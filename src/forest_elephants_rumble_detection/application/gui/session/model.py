from .files import Event, Events, File, ModelInterface
from collections import namedtuple
#from .mlmodel import modelapi
from forest_elephants_rumble_detection.utils import yaml_read
from pathlib import Path
from ultralytics import YOLO
import logging
from forest_elephants_rumble_detection.model.yolo.predict import pipeline

class Model(ModelInterface):
    """Class for analyzing a file by the ML model."""

    def __init__(self, callbacks=[]):
        self.callbacks = callbacks

    def analyze(self, file: File, output_dir:Path):
        """
        Performance inference
        """
        
        config = yaml_read(Path(r"src/forest_elephants_rumble_detection/application/08_artifacts/inference_config.yaml"))

        model = YOLO(config["model_weights_filepath"])
        logging.basicConfig(level=config['loglevel'].upper())

        df_pipeline = pipeline(
            model=model,
            audio_filepaths=[Path(file.path)],
            duration=config["duration"],
            overlap=config["overlap"],
            width=config["width"],
            height=config["height"],
            freq_min=config["freq_min"],
            freq_max=config["freq_max"],
            n_fft=config["n_fft"],
            hop_length=config["hop_length"],
            batch_size=config["batch_size"],
            output_dir=output_dir,
            save_spectrograms=config["save_spectrograms"],
            save_predictions=config["save_predictions"],
            verbose=config["verbose"],
        )

        # Function to map DataFrame to Events
        def map_events(df, event_class):
            events = Events()
            for _, row in df.iterrows():
                if row['instance_class'] == 'rumble':
                    events.rumble.append(Event(
                        start=row['t_start'], end=row['t_end'], freq_start=row['freq_start'], freq_end=row['freq_end'],
                        probability=row["probability"]
                    ))
                elif row['instance_class'] == 'gunshot':
                    events.gunshot.append(Event(
                        start=row['t_start'], end=row['t_end'], freq_start=row['freq_start'], freq_end=row['freq_end'],
                        probability=row["probability"]
                    ))
            return events

        # Apply the function
        file.results = map_events(df_pipeline, 'instance_class')

        file.save()
        
        # all clips in file processed, file.results now contains all audio events that happened in the file
        #print(file.results)
        file.is_analyzed = True




