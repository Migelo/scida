import logging
import sys

# need to import interfaces to register them in registry for loading
# TODO: automatize implicitly
from scida.convenience import load
from scida.customs.arepo.dataset import ArepoSnapshot
from scida.customs.arepo.series import ArepoSimulation
from scida.customs.gadget.gadgetstyle import GadgetStyleSnapshot, SwiftSnapshot
from scida.customs.gizmo.dataset import GizmoSnapshot

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
