import os
from pathlib import Path
from typing import Any, List, Optional, Tuple, Type, Union
from ruamel.yaml.compat import StringIO
import pytimeloop.timeloopfe.v4 as tl
from pytimeloop.timeloopfe.common.nodes import DictNode
from pytimeloop.timeloopfe.v4.art import Art
from pytimeloop.timeloopfe.v4.ert import Ert
import ruamel.yaml
import logging, sys
from numbers import Number
import shutil

logger = logging.getLogger("pytimeloop")
formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s - %(message)s")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def show_config(*paths):
    total = ""
    for path in paths:
        if isinstance(path, str):
            path = Path(path)

        if path.is_dir():
            for p in path.glob("*.yaml"):
                with p.open() as f:
                    total += f.read() + "\n"
        else:
            with path.open() as f:
                total += f.read() + "\n"
    print(total)
    # return total


def run_timeloop_model(jinja_parse_data: dict = None, alt_top=None, **kwargs):
    if os.path.exists("./output_dir"):
        os.system("rm -r ./output_dir")

    run_accelergy(jinja_parse_data, alt_top=alt_top, **kwargs)

    jinja_parse_data = {**(jinja_parse_data or {}), **kwargs}
    spec = tl.Specification.from_yaml_files(
        "top.yaml.jinja2" if alt_top is None else alt_top, jinja_parse_data=jinja_parse_data
    )

    # print(spec)
    # app = tl.to_model_app(spec, output_dir="./output_dir")
    # print('Model app created')
    try:
        return tl.call_model(spec, output_dir="./output_dir")
    except Exception as e:
        raise Exception(str(e).replace("tl model", "timeloop model"))


def run_timeloop_mapper(jinja_parse_data: dict = None, alt_top=None, **kwargs):
    if os.path.exists("./output_dir"):
        os.system("rm -r ./output_dir")

    run_accelergy(jinja_parse_data, alt_top=alt_top, **kwargs)
    jinja_parse_data = {**(jinja_parse_data or {}), **kwargs}
    spec = tl.Specification.from_yaml_files(
        "top.yaml.jinja2" if alt_top is None else alt_top, jinja_parse_data=jinja_parse_data
    )
    try:
        return tl.call_mapper(spec, output_dir="./output_dir")
    except Exception as e:
        raise Exception(str(e).replace("tl mapper", "timeloop mapper"))



def run_accelergy(jinja_parse_data: dict = None, alt_top=None, **kwargs):
    if os.path.exists("./output_dir"):
        os.system("rm -r ./output_dir")
    jinja_parse_data = {**(jinja_parse_data or {}), **kwargs}
    spec = tl.Specification.from_yaml_files(
        "top.yaml.jinja2" if alt_top is None else alt_top, jinja_parse_data=jinja_parse_data
    )
    try:
        result = tl.accelergy_app(spec, output_dir="./output_dir")
    except Exception as e:
        raise Exception(str(e).replace("tl accelergy", "timeloop accelergy"))

    shutil.copy("output_dir/ART.yaml", "output_dir/timeloop-model.ART.yaml")
    shutil.copy("output_dir/ART.yaml", "output_dir/timeloop-mapper.ART.yaml")
    shutil.copy("output_dir/ERT.yaml", "output_dir/timeloop-model.ERT.yaml")
    shutil.copy("output_dir/ERT.yaml", "output_dir/timeloop-mapper.ERT.yaml")

    return result


def check_type(context, a, t):
    pref = f"For {context}, expected "
    if isinstance(t, list):
        check_type(context, a, list)
        assert len(a) == len(
            t
        ), f"{pref} a tuple of length {len(t)}, but got a tuple of length {len(a)}"
        for i, (ai, ti) in enumerate(zip(a, t)):
            check_type(f"{context}[{i}]", ai, ti)
    else:
        assert (
            not isinstance(a, str) or a != "FILL ME"
        ), f"For {context}, expected an answer. Please fill in the answer."
        if not isinstance(t, tuple):
            t = (t,)
        if isinstance(t, tuple) and any(a == ti for ti in t):
            return
        tn = tuple(t0 for t0 in t if isinstance(t0, Type))
        assert isinstance(a, tn), f"{pref} {t}, but got {a} of type {type(a).__name__}"


def check_string(context, a):
    check_type(context, a, str)
    assert (
        len(a) < 120
    ), f"For {context}, expected a string of length < 120, but got a string of length {len(a)}"


def answer(
    question: str,
    subquestion: str,
    answer: Any,
    required_type: Union[type, Tuple[type]],
    assumptions: Optional[List[str]] = None,
):
    check_type("answer", answer, required_type)

    if not assumptions:
        assumptions = []

    check_type("assumptions", assumptions, list)
    check_type("assumptions", assumptions, [str] * len(assumptions))

    for i, a in enumerate(assumptions):
        check_string(f"assumptions[{i}]", a)

    this_dir = os.path.dirname(os.path.realpath(__file__))
    answer_path = os.path.join(this_dir, "answers.yaml")

    yaml = ruamel.yaml.YAML(typ="rt")

    answers = {}
    if os.path.exists(answer_path):
        with open(answer_path, "r") as f:
            answers = yaml.load(f.read())

    answers.setdefault(question, {})
    answers[question][subquestion] = {
        "answer": answer,
        "assumptions": assumptions
    }

    # Sort the answers
    answers = dict(sorted(answers.items(), key=lambda x: x[0]))
    answers[question] = dict(sorted(answers[question].items(), key=lambda x: x[0]))

    s = StringIO()
    yaml.dump(answers, s)

    with open(answer_path, "w") as f:
        f.write(s.getvalue())

    print("\n\t".join([f"{question}: {subquestion}", f"{answer}"] + assumptions))
