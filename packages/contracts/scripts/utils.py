import os
import yaml
import pathlib
import json
import logging


def load_yaml():
    with open("./config.yaml") as f:
        return yaml.safe_load(f)


def load_abi(contract_name: str):
    base_path = pathlib.Path(__file__).parent.parent / "build/contracts"

    for root, ds, fs in os.walk(base_path):
        for f in fs:
            if f.split(".")[0] == contract_name and f == f"{contract_name}.json":
                with open(os.path.join(root, f)) as _f:
                    return json.load(_f)['abi']


def config_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d (%(levelname)s): %(message)s",
        datefmt="%y-%m-%d %H:%M:%S"
    )

    logging.getLogger().setLevel(logging.INFO)
