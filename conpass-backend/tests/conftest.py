import os
import sys

sys.path.append(os.path.join(
    os.path.abspath(os.path.dirname(os.path.abspath(__file__))),
    "../app"
))

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.testing"
