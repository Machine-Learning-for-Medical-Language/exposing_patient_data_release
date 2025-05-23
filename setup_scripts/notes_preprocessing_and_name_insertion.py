"""
Preprocessing for Name De-Identification
=========================================

Setup
-----

1.a Function that takes in all notes of a patient and patient name. Process the notes to add name in.
1.b compose Function from setup 1 with another function that adds patient name to beginning of each sentence.

Main Processing
---------------

2. Script that apply function to every `SUBJECT_ID`

Output of this step should be a mapping

1. `SUBJECT_ID` -> List of Notes (Modified 1.a) --- Store in `SUBJECT_ID_to_NOTES_1a.csv`
2. `SUBJECT_ID` -> List of Notes (Modified 1.b) --- Store in `SUBJECT_ID_to_NOTES_1b.csv`
"""

import re, os
import pandas as pd
from tqdm import tqdm
import swifter

from setup_scripts.notes_preprocessing_functions import preprocess_text

tqdm.pandas()


def replace_text_with_regex(text, name, search_term):
    pattern = re.compile(f"\[\*\*[^\*]*?{search_term}[^\*]*?\*\*\]", re.IGNORECASE)
    return re.sub(pattern, name, text)


def add_name_at_pattern(row):
    first_name = row["FIRST_NAME"]
    last_name = row["LAST_NAME"]
    original_note = row["MOD_TEXT"]

    note = replace_text_with_regex(original_note, first_name, "Known firstname")
    note = replace_text_with_regex(note, last_name, "Known lastname")

    return note


def add_name_at_bos(row):
    first_name = row["FIRST_NAME"]
    last_name = row["LAST_NAME"]
    note = row["MOD_TEXT"]

    note = "\n".join([f"{first_name} {last_name} {sentence}" for sentence in note.split("\n")])

    return note


def run(input_file, input_names, output_csv, replace_pattern_with_name, insert_name_at_bos):
    """Save the data in two different output formats.
    @param input_file  a CSV containing subject_ids to notes (Headers: SUBJECT_ID,TEXT).
    @param input_names a CSV containing a mapping of subject_ids to names (Headers: SUBJECT_ID,FIRST_NAME,LAST_NAME).
    @param output_csv is where to save the CSV (Headers: SUBJECT_ID,TEXT).
    @param insert_name_at_bos should we prepend names to the beginning of every sentence.
    """

    subject_id_to_notes = pd.read_csv(input_file)
    subject_id_to_names = pd.read_csv(input_names)

    subject_id_to_notes = subject_id_to_notes.merge(subject_id_to_names, how="inner", on="SUBJECT_ID")

    subject_id_to_notes["MOD_TEXT"] = subject_id_to_notes.TEXT.apply(lambda x : x)

    if replace_pattern_with_name:
        subject_id_to_notes["MOD_TEXT"] = subject_id_to_notes.progress_apply(add_name_at_pattern, axis=1)
        subject_id_to_notes["MODIFIED"] = subject_id_to_notes.apply(lambda x: x.TEXT != x.MOD_TEXT, axis=1)

    subject_id_to_notes["MOD_TEXT"] = (
        subject_id_to_notes["MOD_TEXT"]
        .swifter.progress_bar(enable=True)
        .allow_dask_on_strings()
        .apply(preprocess_text)
    )

    subject_id_to_notes = subject_id_to_notes[~subject_id_to_notes.MOD_TEXT.isna()]
    subject_id_to_notes = subject_id_to_notes[subject_id_to_notes.MOD_TEXT.apply(lambda x: len(x.strip()) > 0)]

    if insert_name_at_bos:
        subject_id_to_notes["MOD_TEXT"] = subject_id_to_notes.progress_apply(add_name_at_bos, axis=1)

    subject_id_to_notes["TEXT"] = subject_id_to_notes["MOD_TEXT"]

    subject_id_to_notes[["SUBJECT_ID", "CATEGORY", "FIRST_NAME", "LAST_NAME", "CHARTDATE", "CHARTTIME", "TEXT"]].to_csv(output_csv, index=False)

    if replace_pattern_with_name and not insert_name_at_bos:
        print("Num Modified", subject_id_to_notes[subject_id_to_notes.MODIFIED].SUBJECT_ID.unique().size)
        subject_id_to_notes[subject_id_to_notes.MODIFIED][["SUBJECT_ID"]].drop_duplicates().to_csv(
            os.path.join(os.path.dirname(output_csv), "reidentified_subject_ids.csv"), index=False
        )


from argparse import ArgumentParser

if __name__ == "__main__":
    """
    Usage:
        - python note_name_insertion.py --input-file SUBJECT_ID_to_NOTES_original.csv \
                                        --input-names subject_id_to_name.csv \
                                        --output-csv SUBJECT_ID_to_NOTES_1a.csv \
                                        [--insert-name-at-bos]

    Output Format #1:
        SUBJECT_ID,TEXT,MODIFIED
        249,note 1, 0
        249,note 2, 0
        249,note 3, 1
        250,note 4, 0
        250,note 5, 1
    """

    parser = ArgumentParser()
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--input-names", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--replace-pattern-with-name", action="store_true")
    parser.add_argument(
        "--insert-name-at-bos", action="store_true", help="Specify this to add name at beginning of sentence"
    )

    args = parser.parse_args()
    run(
        args.input_file,
        args.input_names,
        args.output_csv,
        args.replace_pattern_with_name,
        args.insert_name_at_bos,
    )
    print(f"Insertion Done and Saved at {args.output_csv}")
