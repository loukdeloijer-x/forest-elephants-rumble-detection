from pathlib import Path
# from types import List

import pandas as pd

class Session:

    def __init__(self, input_folder: str, output_folder: str) -> None:
        """Determines all input WAVs, the WAVs that remains to be processed, and the output TXTs to be generated

        Args:
            input_folder (str): _description_
            output_folder (str): _description_
        """
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)

        self.all_input_wav = self._set_all_input_wav()

        tmp_output_annotation_txt_path = self.output_folder / f'{self.input_folder.stem}_annotation.txt' 
        tmp_output_summary_txt_path = self.output_folder / f'{self.input_folder.stem}_summary.txt' 
        self.output_annotation_txt = tmp_output_annotation_txt_path
        self.output_summary_txt = tmp_output_summary_txt_path

        self.annotation_df = self._initialize_annotation_df()  # TODO remove
        self.summary_df = self._initialize_summary_df()
        self.remaining_input_wav = self.update_remaining_wav()

    def _set_all_input_wav(self) -> list:
        return list(map(str, self.input_folder.rglob(pattern='*.wav')))  #, case_sensitive=False))

    @staticmethod
    def _sanity_check_df(df: pd.DataFrame, col_ls=None) -> bool:
        if len(df.index) == 0:
            return False
        return True

    @staticmethod
    def _sanity_check_file(path_to_file: Path) -> bool:
        if not path_to_file.exists():
            return False
        if path_to_file.stat().st_size <= 0:
            return False
        return True

    def _load_and_check_df(self, path_to_file: Path, col_ls=None, sep='\t') -> bool:
        input_is_good = False
        existing_df = pd.DataFrame()
        if self._sanity_check_file(path_to_file):
            try:
                existing_df = pd.read_csv(path_to_file, sep=sep)
            except Exception:
                raise
            if self._sanity_check_df(existing_df, col_ls):
                input_is_good = True
        return input_is_good, existing_df

    def _initialize_annotation_df(self) -> pd.DataFrame:
        input_is_good, existing_df = self._load_and_check_df(self.output_annotation_txt)
        if not existing_df.empty:
            existing_df = existing_df.set_index('Selection')
        return existing_df

    def _initialize_summary_df(self) -> pd.DataFrame:
        input_is_good, existing_df = self._load_and_check_df(self.output_summary_txt)
        if not existing_df.empty:
            existing_df = existing_df.set_index('Begin Path')
        else:
            dtype_spec={"File Duration (s)": float, "Rumble Count": int, "Gunshot Count": int}
            existing_df = pd.DataFrame(columns=dtype_spec.keys()).astype(dtype_spec)
            existing_df.index.name = 'Begin Path'
        return existing_df

    def _compare_annotation_and_summary(self):
        pass

    def update_remaining_wav(self) -> list:  # TODO fix it
        if len(self.summary_df.index):
            tmp_processed_wav_ls = self.summary_df.reset_index()['Begin Path'].drop_duplicates().tolist()
            return [i_path for i_path in self.all_input_wav if i_path not in tmp_processed_wav_ls]
        else:
            return self.all_input_wav
            
    def update_annotation_df(self, input_df: pd.DataFrame) -> None:
        # TODO remove
        if self.annotation_df.empty:
            self.annotation_df = input_df.copy(deep=True)
        else:
            self.annotation_df = (
                pd.concat([self.annotation_df, input_df])
            )
            self.annotation_df.index = range(1, len(self.annotation_df.index) + 1)
            self.annotation_df.index.name = input_df.index.name
            # self.annotation_df.index += 1  # make it start from 1

    def save_annotation_df(self):
        # TODO remove
        # 1. save to a tmp file
        # 2. copy the tmp file to self.output_annotation_txt
        self.annotation_df.to_csv(self.output_annotation_txt, sep='\t')

    def update_summary_df(self, file):
        #  “Begin Path”, “File Duration (s)”, “Rumble Count”, “Gunshot Count”, 

        self.summary_df.loc[file.path] = pd.Series(
            {
                "File Duration (s)": file.duration,
                "Rumble Count": len(file.results.rumble), 
                "Gunshot Count": len(file.results.gunshot)
            }
        )
    def save_summary_df(self):
        # TODO more robust approach
        # 1. save to a tmp file
        # 2. copy the tmp file to self.output_summary_txt
        self.summary_df.to_csv(self.output_summary_txt, sep='\t')

    def update_annotation_txt(self, input_df: pd.DataFrame):
        out_df = input_df.copy()
        if not self.summary_df.empty:
            # Edit columns of out_df based on summary_df
            # As specified in 3.2.3.1 of https://docs.google.com/document/d/1z9wtIQMTTftHeqgv5COLFLLGaeteyzL4sw_-9ysqqxA/edit
            out_df.index += self.summary_df[["Rumble Count", "Gunshot Count"]].sum().sum()
            cumulative_duration_n = self.summary_df["File Duration (s)"].sum()
            out_df["Begin Time (s)"] += cumulative_duration_n
            out_df["End Time (s)"] += cumulative_duration_n
        out_df.index = out_df.index.astype(int)
        out_df.to_csv(self.output_annotation_txt, sep='\t', mode='a', header=not self.output_annotation_txt.exists())



