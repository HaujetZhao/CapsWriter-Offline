from typing import Any, TypeAlias

from numpy import ndarray

RecordingData: TypeAlias = ndarray[Any, Any]
# #TODO-REF: in the end we are converting RecordingData to bytes so maybe
#   using bytes directly can reduce the overhead.
