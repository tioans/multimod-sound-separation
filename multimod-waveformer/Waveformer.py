import argparse
import os, pickle

import numpy as np

import torch
import torchaudio
import wget

from src.helpers import utils
from src.training.dcc_tf import Net as Waveformer

TARGETS = [
    "Acoustic_guitar",
    "Applause",
    "Bark",
    "Bass_drum",
    "Burping_or_eructation",
    "Bus",
    "Cello",
    "Chime",
    "Clarinet",
    "Computer_keyboard",
    "Cough",
    "Cowbell",
    "Double_bass",
    "Drawer_open_or_close",
    "Electric_piano",
    "Fart",
    "Finger_snapping",
    "Fireworks",
    "Flute",
    "Glockenspiel",
    "Gong",
    "Gunshot_or_gunfire",
    "Harmonica",
    "Hi-hat",
    "Keys_jangling",
    "Knock",
    "Laughter",
    "Meow",
    "Microwave_oven",
    "Oboe",
    "Saxophone",
    "Scissors",
    "Shatter",
    "Snare_drum",
    "Squeak",
    "Tambourine",
    "Tearing",
    "Telephone",
    "Trumpet",
    "Violin_or_fiddle",
    "Writing",
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input", type=str, default=None, help="Path to the input audio file."
    )
    parser.add_argument(
        "output",
        type=str,
        default=None,
        help="Path to the output audio file (output is written in the .wav format).",
    )
    parser.add_argument(
        "--targets",
        nargs="+",
        type=str,
        default=[],
        help="Targets to output. Pick a subset of: %s" % TARGETS,
    )
    args = parser.parse_args()

    if not os.path.exists("default_config.json"):
        config_url = "https://targetsound.cs.washington.edu/files/default_config.json"
        print("Downloading model configuration from %s:" % config_url)
        wget.download(config_url)

    if not os.path.exists("default_ckpt.pt"):
        ckpt_url = "https://targetsound.cs.washington.edu/files/default_ckpt.pt"
        print("\nDownloading the checkpoint from %s:" % ckpt_url)
        wget.download(ckpt_url)

    # Instantiate model
    params = utils.Params("default_config.json")
    model = Waveformer(**params.model_params)
    if torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    model.load_state_dict(
        torch.load("default_ckpt.pt", map_location=device)["model_state_dict"]
    )
    model.to(device).eval()

    # Read input audio
    mixture, fs = torchaudio.load(args.input)
    if fs != 44100:
        mixture = torchaudio.functional.resample(mixture, orig_freq=fs, new_freq=44100)
    mixture = mixture.unsqueeze(0).to(device)
    print("Loaded input audio from %s" % args.input)

    # Construct the query vector
    # if len(args.targets) == 0:
    #     query = torch.ones(1, len(TARGETS))
    # else:
    #     query = torch.zeros(1, len(TARGETS))
    #     for t in args.targets:
    #         query[0, TARGETS.index(t)] = 1.0

    # Load precomputed embeddings
    with open('emb-imagebind-orig.pickle', 'rb') as handle:
        embeddings = pickle.load(handle)

    embedding_mod = "text"
    embedding_len = len(embeddings["text"][0])  # get emb dim    

    # Construct the query embedding vector
    if len(args.targets) == 0:
        # case with no target
        query = torch.ones(1, len(embedding_len)) 
    elif len(args.targets) == 1:
        # case with single target
        query = embeddings[embedding_mod][TARGETS.index(t)]
    else:
        # case with multiple targets
        emb_list = []
        for t in args.targets:
            emb_list.append(embeddings[embedding_mod][TARGETS.index(t)])

        # average the embeddings
        query = np.mean(emb_list, axis=0)
    
    # print("QUERY SHAPE: ", query.shape)
    
    with torch.inference_mode():
        output = model(mixture.to(device), query.to(device), mode="test").squeeze(0).cpu()
    if fs != 44100:
        output = torchaudio.functional.resample(output, orig_freq=44100, new_freq=fs)
    print("Inference done. Saving output audio to %s" % args.output)

    assert not os.path.exists(args.output), "Output file already exists."
    torchaudio.save(args.output, output, fs)
