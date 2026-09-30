import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))  # repo root -> custom_components
sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "tests"))  # pbwrite
