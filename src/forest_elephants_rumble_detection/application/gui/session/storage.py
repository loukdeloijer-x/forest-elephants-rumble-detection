import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from .files import Event, Events, File, FileManager, StorageInterface


def hash(str):
    return hashlib.sha1(bytes(str, "utf-8")).hexdigest()


@dataclass
class StorageInfo:
    name: str
    path: str
    duration: float
    sample_rate: int
    is_analyzed: bool
    part_analyzed: float
    subdir: str
    numrumble: int
    numgunshot: int

    def dict(self):
        return asdict(self)

    @classmethod
    def from_file(cls, file: File):
        return cls(
            name=file.name,
            path=str(file.path),  # FG
            duration=file.duration,
            sample_rate=file.sample_rate,
            is_analyzed=file.is_analyzed,
            part_analyzed=file.part_analyzed,
            subdir=hash(str(file.path)),  # FG
            numrumble=len(file.results.rumble),
            numgunshot=len(file.results.gunshot),
        )

    def to_file(self, results=None, file_manager=None):
        f = File(
            name=self.name,
            path=str(self.path),
            path_2=Path(str(self.path)),
            duration=self.duration,
            sample_rate=self.sample_rate,
            is_analyzed=self.is_analyzed,
            part_analyzed=self.part_analyzed,
            results=results,
            file_manager=file_manager,
        )
        f.storage = self
        return f


class Storage(StorageInterface):
    """Class that handles storing and exporting information."""

    def __init__(self, app_data_dir=None):
        self.app_data_dir = app_data_dir
        if self.app_data_dir is not None:
            self.app_data_dir = Path(self.app_data_dir)
            assert self.app_data_dir.is_dir(), "Given app data directory not found."

    def _save_events(self, events, start, event, subdir):
        for i, e in enumerate(events[start:], start=start):
            filename = self.app_data_dir / subdir / event / (str(i) + ".json")
            with open(filename, "w") as f:
                json.dump({"start": e.start, "end": e.end}, f)

    def _load_events(self, dirname, event):
        events = []
        path = Path(dirname / event)
        if path.is_dir():
            for filepath in path.iterdir():
                if str(filepath).endswith(".json"):
                    print("loading:", filepath)
                    with open(filepath) as f:
                        e = json.load(f)
                events.append(Event(**e))
        return events

    def _save_info(self, storage_info, subdir):
        filename = self.app_data_dir / subdir / "info.json"
        with open(filename, "w") as f:
            json.dump(storage_info, f)

    def _load_info(self, dirname):
        filename = dirname / "info.json"
                
        with open(filename) as f:
            info = json.load(f)
        return StorageInfo(**info)

    def _mksubdirs(self, subdir):
        (self.app_data_dir / subdir / "rumble").mkdir(exist_ok=True, parents=True)
        (self.app_data_dir / subdir / "gunshot").mkdir(exist_ok=True, parents=True)

    def save(self, file):  # FG saves detected events (both rumbles and gunshots) to a JSON file called info.JSON
        if self.app_data_dir is not None:
            if hasattr(file, "storage") and file.storage is not None:  # FG
                subdir = file.storage.subdir
                numrumble = file.storage.numrumble
                numgunshot = file.storage.numgunshot
                rumbles = file.results.rumble
                gunshots = file.results.gunshot
                # save "new" events in file.results i.e. from the saved nums onward
                self._save_events(rumbles, start=numrumble, event="rumble", subdir=subdir)
                self._save_events(gunshots, start=numgunshot, event="gunshot", subdir=subdir)
                # update the storage
                file.storage.numrumble = len(rumbles)
                file.storage.numgunshot = len(gunshots)
                file.storage.part_analyzed = file.part_analyzed
                file.storage.is_analyzed = file.is_analyzed
                self._save_info(file.storage.dict(), subdir)

            else:
                subdir = hash(str(file.path))  # FG
                self._mksubdirs(subdir)
                file.storage = StorageInfo.from_file(file)
                self._save_info(file.storage.dict(), subdir)

                rumbles = file.results.rumble
                gunshots = file.results.gunshot
                # save all events in the file.results
                self._save_events(rumbles, start=0, event="rumble", subdir=subdir)
                self._save_events(gunshots, start=0, event="gunshot", subdir=subdir)

    def load_files(self, file_manager: FileManager):
        if self.app_data_dir is None:
            return []
        else:
            for dirname in self.app_data_dir.iterdir():
                info = self._load_info(dirname)
                rumbles = self._load_events(dirname, "rumble")
                gunshots = self._load_events(dirname, "gunshots")
                results = Events(rumble=rumbles, gunshot=gunshots)
                file = info.to_file(results, file_manager)
                yield file

    def remove_file(self, file):  # FG remove the temporary folders containing the saved Events
        path = self.app_data_dir / file.storage.subdir
        print("Removing", path)
        shutil.rmtree(path)