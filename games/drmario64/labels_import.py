"""DIRTY ROOM (one-off): turn transcription sheets into the two clean inputs.

    python -m games.drmario64.labels_import <tx dir with label_boxes.json, crop_index.json, sNN.txt>

spec/label_boxes.json   {texture: {box index: [x, y, w, h, ink, edge, plate]}}  (only transcribed boxes)
tex_labels.json         {"texture#index": "words"}                          (the words, as the game shows them)
Transcription syntax (kept in the words):  a|b lines · a||b equal cells · <, > horizontal align ·
^, _ top/bottom · {n} text height · +x merge into the overlapping box · text@N extend over box N.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main(argv):
    tx = argv[1]
    boxes = json.load(open(os.path.join(tx, "label_boxes.json")))
    index = json.load(open(os.path.join(tx, "crop_index.json")))
    words, keep = {}, {}
    for f in sorted(glob.glob(os.path.join(tx, "s*.txt"))):
        for line in open(f, encoding="utf-8"):
            if not line.strip():
                continue
            num, text = line.rstrip("\n").split("\t", 1)
            key = index[num]
            if "@" in text:
                text, other = text.rsplit("@", 1)
                tex = key.split("#")[0]
                text += "@" + index[other].split("#")[1]
                keep.setdefault(tex, {})[index[other].split("#")[1]] = boxes[tex][int(index[other].split("#")[1])]
            words[key] = text
            tex, k = key.split("#")
            keep.setdefault(tex, {})[k] = boxes[tex][int(k)]
    from games.drmario64 import stacks          # mask-paired texts are drawn by stacks.py
    words = {k: v for k, v in words.items() if k.split("#")[0] not in stacks.BY_NAME}
    keep = {k: v for k, v in keep.items() if k not in stacks.BY_NAME}
    json.dump(keep, open(os.path.join(HERE, "spec", "label_boxes.json"), "w"), indent=0)
    json.dump(words, open(os.path.join(HERE, "tex_labels.json"), "w", encoding="utf-8"), indent=0, ensure_ascii=False)
    print(f"{len(words)} labels in {len(keep)} textures")


if __name__ == "__main__":
    main(sys.argv)
