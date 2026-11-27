"""spaCy loading, set up so the same text always gives the same parse.

The model version is pinned in ``pyproject.toml``. Two more settings keep the
parse stable: BLAS runs on one thread, because a multi-threaded matrix
product may sum in a different order from run to run, and each segment is
parsed on its own, so the files that are linted together cannot change the
parse of any one of them.
"""

from __future__ import annotations

import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "BLIS_NUM_THREADS"):
    os.environ[_var] = "1"

MODEL = "en_core_web_sm"
MODEL_VERSION = "3.8.0"

_nlp = None


def load():
    global _nlp
    if _nlp is None:
        import spacy

        nlp = spacy.load(MODEL, exclude=["ner"])
        version = nlp.meta.get("version")
        if version != MODEL_VERSION:
            raise RuntimeError(
                f"prose-lint needs {MODEL} {MODEL_VERSION}, but {version} is installed; "
                "results would differ from other installations"
            )
        _nlp = nlp
    return _nlp


def parse(text: str):
    return load()(text)
