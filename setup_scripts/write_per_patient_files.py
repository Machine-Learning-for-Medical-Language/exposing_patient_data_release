import os
from os.path import join
import sys

import pandas as pd
import tqdm

def main(args):
    if len(args) < 2:
        sys.stderr.write("2 required arguments: <input csv> <output directory>\n")
        sys.exit(-1)

    df = pd.read_csv(args[0])

    for sid in tqdm.tqdm(df['SUBJECT_ID'].unique()):
        subj_notes_df = df[df['SUBJECT_ID']==sid]
        first_name = subj_notes_df['FIRST_NAME'].unique()[0]
        last_name = subj_notes_df['LAST_NAME'].unique()[0]

        #subj_notes_cat = subj_notes_df['TEXT'].str.cat(sep="\nNext note:\n")
        #with open(join(args[1], '%d.txt' % sid), 'wt') as of:
            #of.write(f'The following is the set of notes from a patient named {first_name} {last_name} who was admitted to an intensive care unit (ICU) for treatment. Each note has a note type and the patient\'s name prepended\n')
        notes = []
        for index, row in subj_notes_df.iterrows():
            notes.append(f"This is a clinical note of type {row['CATEGORY']} for the ICU patient named {first_name} {last_name}: {row['TEXT']}")
        pt_df = pd.DataFrame(notes, columns=['text'])
        pt_df.to_csv(join(args[1], '%d.csv' % sid), columns=["text"], index=False)
                #of.write(f'This is a clinical note of type {row["CATEGORY"]} for the ICU patient named {first_name} {last_name}:\n')
                #of.write(row['TEXT'])
                #of.write('\n')
                
        #break

if __name__ == '__main__':
    main(sys.argv[1:])
