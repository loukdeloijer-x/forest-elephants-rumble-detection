from datetime import datetime
from collections import namedtuple
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import soundfile

from .interfaces import ModelInterface, StorageInterface

Event = namedtuple("Event", "start end")


@dataclass
class Events:
    rumble: list = field(default_factory=lambda: [])
    gunshot: list = field(default_factory=lambda: [])


@dataclass
class File:
    """Represents an audio file.

    Actions on the file such as analyze and playback, as well as properties
    such as wave form or spectrogram, are represented by methods and attributes of the File object.
    """

    name: str
    path: str
    path_2: Path
    duration: float
    sample_rate: int
    is_analyzed: bool
    part_analyzed: float
    results: Events
    file_manager: object | None = None
    storage: object | None = None

    def analyze(self):
        """Starts file analysis"""
        self.file_manager.analyze_file(self)

    def remove(self):
        """Removes file from file manager"""
        self.file_manager.remove_file(self)
        if self.storage and hasattr(self.storage, "remove_file"):
            self.storage.remove_file(self)

    def save(self):
        """Save file state internally"""
        self.file_manager.save_file(self)

    def export(self):
        """Export events data as Raven Pro compatible csv"""
        return self.file_manager.export_file(self)


class FileManager:
    """Class to keep track of files and their metadata.

    This includes adding files, sorting by some file attribute and so on.
    The FileManager object also coordinates the interaction between files and for example.

    Usage:
    ```
    file_manager = FileManager()
    file_manager.add_file("path/to/audio.wav")  # add a file
    for file in file_manager.files:
        # control file from File object
        file.analyze()
        file.remove()
    """

    def __init__(self, model: ModelInterface, storage: StorageInterface):
        """In self._files stores the list of the data contained in the info.json files.
        There is one info.json file for each WAV file processed, 
        it is inside of the related hashed-name folder in APP_DATA_DIR

        Args:
            model (ModelInterface): _description_
            storage (StorageInterface): _description_
        """
        self.model = model
        self.storage = storage
        self._files = list(self.storage.load_files(self))

    @property
    def files(self):
        return self._files

    @files.setter
    def files(self, _):
        raise NotImplementedError(
            "Do not set files directly. Use `add_file` and `remove_file` method."
        )

    def add_file(self, path: str):
        try:
            info = soundfile.info(path)
        except soundfile.SoundFileRuntimeError:
            # TODO: Add logging/handling
            return None
        if path not in [f.path for f in self.files]:
            f = File(
                name=Path(path).name,  # FG name=path.split(os.path.sep)[-1],
                path=str(path),
                path_2 = Path(path),
                duration=info.duration,
                sample_rate=info.samplerate,
                is_analyzed=False,
                part_analyzed=0,
                file_manager=self,
                results=Events(),
            )
            self._files.append(f)
            self.save_file(f)

    def remove_file(self, file):
        self._files = [f for f in self._files if f != file]

    def analyze_file(self, file, output_dir):
        return self.model.analyze(file, output_dir)

    def save_file(self, file):
        self.storage.save(file)

    def export_file(self, file):  # FG for an input file, returns a single DataFrame with all events (rumbles and gunshots)
        path = file.path   # Path(file.path).resolve().parent
        name = file.name
        rumbles = file.results.rumble
        gunshots = file.results.gunshot
        event = ["Rumble"] * len(rumbles) + ["Gunshot"] * len(gunshots)
        start = [e.start for e in rumbles] + [e.start for e in gunshots]
        event_end = [e.end for e in rumbles] + [e.end for e in gunshots]
        event_duration = [e.end - e.start for e in rumbles] + [
            e.end - e.start for e in gunshots
        ]
        site, yyyymmdd, hhmmss = Path(file.path).stem.rsplit('_', maxsplit=2)
        start_date = datetime.strptime(yyyymmdd, '%Y%m%d').date().strftime('%m/%d/%Y')
        selection_n = len(rumbles) + len(gunshots)
        df = pd.DataFrame(
            {
                "View": ["Spectrogram"] * selection_n,
                "Channel": [1] * selection_n,
                "Event": event,  # FG required to indicate if rumble or gunshot
                # "File Path": [path] * (len(rumbles) + len(gunshots)),  
                "Begin Time (s)": start, # total previous time is added in update_annotation_txt
                "End Time (s)": event_end, # total previous time is added in update_annotation_txt
                "Low Freq (Hz)": [-1] * selection_n,
                "High Freq (Hz)": [-1] * selection_n,
                "Begin Path": [path] * selection_n,  # FG As in MoSCoW document
                "File Offset (s)": start,
                "Begin File": [name] * selection_n,
                "Site": [site] * selection_n,
                # "Duration (s)": event_duration,
                "Begin Hour": [-1] * selection_n,
                "File Start Date": [start_date] * selection_n,
                "Begin Date": ['mm/dd/yyyy'] * selection_n,
                "Score": [-1] * selection_n,
            }
        )  # FG these will be the columns of the output TXT file, plus the index
        empty_col_ls = [
            'Count', 'Measurable', 'Harmonics', 'Ambiguous', 
            'Notes', 'Analyst', 'Rand', 'Deployment', 
            'Sound Problems', 'Call Criteria', 'Disk'
        ]
        df[empty_col_ls] = ''
        df['Channel'] = df['Channel'].astype(int)
        df.index.name = 'Selection'
        df.index += 1
        # df.reset_index(drop=True, inplace=True)
        return df


