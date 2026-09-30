import pathlib
import sys

# the protocol lib lives inside the integration but has no Home Assistant imports
sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "custom_components" / "resmed_airsense"))
