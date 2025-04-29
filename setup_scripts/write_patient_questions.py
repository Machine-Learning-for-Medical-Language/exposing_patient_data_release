import os
from os.path import join
import sys

import pandas as pd
from pandas.tseries.offsets import DateOffset
import tqdm
import json
import requests
import csv

def is_valid_json(json_str):
    try:
        parsed = json.loads(json_str)
        return True, parsed
    except json.JSONDecodeError as e:
        return False, str(e)

def is_correct_format(parsed_json):
    if not isinstance(parsed_json, dict):
        return False, "Not a dictionary"
    
    top_level_keys = list(parsed_json.keys())
    if not "Questions" in top_level_keys:
        return False, "No \"Questions\" top level key"
    elif len(top_level_keys) > 1:
        return False, "Too many top-level keys"

    questions = parsed_json["Questions"]
    if not isinstance(questions, list):
        return False, "\"Questions\" should be a list"
        
    for question in questions:
        keys = set(question.keys())
        if not "Question" in keys:
            return False, "No \"Question\" in a question"
        if not "Answer" in keys:
            return False, "No \"Answer\" in a question"
        if not "Difficulty" in keys:
            return False, "No \"Difficulty\" in a question"

        if len(keys) > 3:
            return False, "Unexpected field in \"Question\""

        return True, None

MODEL = "gemma3:4b"  # or "mistral", etc.
#URL = "http://localhost:11434/api/generate"
URL = "http://gpu-10-0:33863/api/generate"

def main(args):
    if len(args) < 2:
        sys.stderr.write("2 required arguments: <input csv> <output file>\n")
        sys.exit(-1)

    df = pd.read_csv(args[0])
    df['CHARTDATE'] = pd.to_datetime(df['CHARTDATE'])
    df['CHARTTIME'] = pd.to_datetime(df['CHARTTIME'])
    df_sorted = df.sort_values(by=['SUBJECT_ID', 'CHARTTIME'])
    pt_year_offsets = dict()
    
    with open(args[1], "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["Patient", "Difficulty", "Question", "Answer"])
        writer.writeheader()
        count = 0
        for sid in tqdm.tqdm(df['SUBJECT_ID'].unique()):
            count += 1
            subj_notes_df = df[df['SUBJECT_ID']==sid].sort_values(by=["SUBJECT_ID", "CHARTTIME"])
            first_name = subj_notes_df['FIRST_NAME'].unique()[0]
            last_name = subj_notes_df['LAST_NAME'].unique()[0]
    
            for index, row in subj_notes_df.iterrows():
                if not sid in pt_year_offsets:
                    year_offset = row["CHARTTIME"].year - 2018
                    pt_year_offsets[sid] = year_offset

                row["CHART_TIMESTAMP"] = (row["CHARTTIME"] - DateOffset(years=pt_year_offsets[sid]))
                note_date = row["CHART_TIMESTAMP"].strftime("%Y-%m-%d")
                note_text = row["TEXT"]
                note_type = row["CATEGORY"]
                try:
                    note_time = row["CHART_TIMESTAMP"].strftime('%I:%M %p')
                except:
                    note_time = "unknown time"
                
                prompt = f"The following is a clinical note of type {note_type} for a patient named {first_name} {last_name} written on {note_date} at {note_time}. We are using these notes to generate a dataset of questions and answers that we will use to quiz medical students in understanding patient charts. Please generate up to three questions about this note, with varying levels of difficulty (Easy, Moderate, Difficult). The question should be self-contained, that is, contain information about the patient it's asking about and the date and approximate time of the information it's requesting. Your output should contain a clean JSON data structure (Do not include markdown, labels, or code fences), using the following schema: {{ \"Questions\": [\"Question\": <question text>, \"Answer\": <expected answer>, \"Difficulty\": <difficulty level>], ... }}. Here is the text of the note: <note> {note_text} </note>" 
                #headers: \"Question\", \"Anwer\", and \"Difficulty\". Here is the text of the note: <note> {note_text} </note>"
                
                
                response = requests.post(URL, json={
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False  # You can also use True if you want streamed responses
                })
                if response.ok:
                    result = response.json()["response"]
                    if result.startswith("```json"):
                        result = result[8:-4]
                    format_ok, parsed_or_error = is_valid_json(result)
                    if not format_ok:
                        print("Received invalid json: %s" % (parsed_or_error))
                        continue
                    schema_ok, schema_msg = is_correct_format(parsed_or_error)
                    if not schema_ok:
                        print("Received wrong schema: %s" % (schema_msg))
                        continue
                    
                    for x in parsed_or_error["Questions"]:
                        x["Patient"] = sid
    
                    #valid_questions.extend(result["Questions"])

                    writer.writerows(parsed_or_error["Questions"])
            if count > 10:
                print("Quitting after 10 patients for debugging")
                return


if __name__ == '__main__':
    main(sys.argv[1:])
