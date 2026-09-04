#!/usr/bin/env python3
"""
verify_lib — every number in a lesson gets computed before it gets written.

The rule this exists to enforce (SKILL.md, กฎเหล็ก 3): for Chemistry, Physics
and Mathematics, no answer, no intermediate value and no "roughly" appears in a
lesson unless Python produced it and, where the sheet gives an answer, it agreed
with the sheet. A confidently wrong worked solution is worse than no solution —
it teaches a method that will be reproduced under exam pressure.

Typical use, in a throwaway `verify.py` inside the working directory:

    from verify_lib import V, ice, kp_from_kc

    v = V(subject="chem", chapter="บทที่ 9 สมดุล")

    x  = ice(K=0.0125, init={"N2O4": 0.100}, rxn="N2O4 -> 2 NO2")
    v.check("ตย. 9.17 [NO2] ที่สมดุล", x["NO2"], expect=0.0316,
            tol=0.02, source="ชีทหน้า 12")

    v.save()          # writes verify_out.json; exits 1 if anything disagrees

`v.save()` failing is a hard stop: preflight refuses to pass a workspace whose
verify_out.json contains a FAIL, or whose numbers were never checked at all.
"""

from __future__ import annotations

import json
import math
import pathlib
import re
import sys
from dataclasses import dataclass, field, asdict

try:
    import sympy as sp
except ImportError:  # pragma: no cover - environment guard
    sys.exit("error: sympy missing — run install.sh")

R_ATM = 0.08206  # L·atm/(mol·K)


# --------------------------------------------------------------------------
# the ledger
# --------------------------------------------------------------------------
@dataclass
class Entry:
    label: str
    got: float | str
    expect: float | str | None
    tol: float | None
    source: str
    status: str


@dataclass
class V:
    subject: str
    chapter: str = ""
    entries: list[Entry] = field(default_factory=list)
    out: pathlib.Path = pathlib.Path("verify_out.json")

    def check(self, label, got, expect=None, tol=0.02, source=""):
        """Record a computed value, optionally against the sheet's own answer.

        `expect=None` is allowed and means "the sheet gives no answer here" —
        it is recorded as COMPUTED, never as PASS, so the distinction survives
        into preflight and nobody can mistake an unchecked number for a
        verified one.
        """
        if expect is None:
            status = "COMPUTED"
        elif isinstance(got, str) or isinstance(expect, str):
            status = "PASS" if str(got).strip() == str(expect).strip() else "FAIL"
        else:
            got_f, exp_f = float(got), float(expect)
            if exp_f == 0:
                ok = abs(got_f) < 1e-12
            else:
                ok = abs(got_f - exp_f) / abs(exp_f) <= tol
            status = "PASS" if ok else "FAIL"

        self.entries.append(Entry(label, got, expect, tol, source, status))
        mark = {"PASS": "✓", "FAIL": "✗", "COMPUTED": "·"}[status]
        detail = f"  (sheet: {expect})" if expect is not None else ""
        print(f"{mark} {label}: {got}{detail}")
        return got

    def save(self) -> None:
        failed = [e for e in self.entries if e.status == "FAIL"]
        payload = {
            "subject": self.subject,
            "chapter": self.chapter,
            "counts": {
                "pass": sum(e.status == "PASS" for e in self.entries),
                "computed": sum(e.status == "COMPUTED" for e in self.entries),
                "fail": len(failed),
            },
            "entries": [asdict(e) for e in self.entries],
        }
        self.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        c = payload["counts"]
        print(f"\n{c['pass']} pass · {c['computed']} computed · {c['fail']} FAIL  → {self.out}")
        if failed:
            print("\nDisagrees with the sheet — do not write these into a lesson:")
            for e in failed:
                print(f"  ✗ {e.label}: got {e.got}, sheet says {e.expect}  [{e.source}]")
            sys.exit(1)


# --------------------------------------------------------------------------
# solving
# --------------------------------------------------------------------------
def solve_for(equation, symbol: str = "x", lo=None, hi=None, positive=True):
    """Solve one equation for one unknown and return the single physical root.

    Raises rather than guessing when the answer is ambiguous — an ICE table
    that yields two admissible roots means the setup is wrong, and silently
    taking the first one is how a wrong method gets taught.
    """
    if isinstance(equation, str):
        x = sp.Symbol(symbol, real=True)
        lhs, _, rhs = equation.partition("=")
        expr = sp.sympify(lhs) - sp.sympify(rhs or "0")
    else:
        # already a sympy Eq or expression — used by ice(), where building the
        # equation as text would mean round-tripping through a parser for nothing
        expr = equation.lhs - equation.rhs if isinstance(equation, sp.Eq) else equation
        syms = [s for s in expr.free_symbols if s.name == symbol]
        x = syms[0] if syms else sp.Symbol(symbol, real=True)
    roots = [sp.nsimplify(r) for r in sp.solve(sp.Eq(expr, 0), x)]

    good = []
    for r in roots:
        if not r.is_real:
            continue
        val = float(r)
        if positive and val < 0:
            continue
        if lo is not None and val < lo - 1e-12:
            continue
        if hi is not None and val > hi + 1e-12:
            continue
        good.append(val)

    if not good:
        raise ValueError(f"no physical root for {equation!r} (roots: {roots})")
    if len(good) > 1:
        raise ValueError(
            f"{len(good)} admissible roots for {equation!r}: {good} — "
            "narrow the range with lo=/hi=, the setup is under-constrained"
        )
    return good[0]


_TERM = re.compile(r"^\s*(\d*)\s*([A-Za-z][A-Za-z0-9()]*)\s*$")


def _side(text: str) -> list[tuple[int, str]]:
    out = []
    for part in text.split("+"):
        m = _TERM.match(part)
        if not m:
            raise ValueError(f"cannot read species {part!r}")
        out.append((int(m.group(1) or 1), m.group(2)))
    return out


def ice(K: float, init: dict, rxn: str, solid: tuple = ()):  # noqa: N803
    """Solve an ICE table for `rxn` written as 'a A + b B -> c C + d D'.

    Returns every species' equilibrium concentration plus the extent x.
    Species listed in `solid` are pure solids/liquids and are left out of K,
    which is the trap the Chemistry sheet sets over and over.
    """
    left_txt, _, right_txt = rxn.partition("->")
    if not right_txt:
        raise ValueError("write the reaction as 'A + B -> C + D'")
    left, right = _side(left_txt), _side(right_txt)

    x = sp.Symbol("x", real=True)
    conc = {}
    for coeff, sp_name in left:
        conc[sp_name] = sp.Float(init.get(sp_name, 0.0)) - coeff * x
    for coeff, sp_name in right:
        conc[sp_name] = sp.Float(init.get(sp_name, 0.0)) + coeff * x

    num = sp.Integer(1)
    for coeff, sp_name in right:
        if sp_name not in solid:
            num *= conc[sp_name] ** coeff
    den = sp.Integer(1)
    for coeff, sp_name in left:
        if sp_name not in solid:
            den *= conc[sp_name] ** coeff

    # x cannot drive any concentration negative — that is the physical bound.
    hi = min(
        [float(init.get(n, 0.0)) / c for c, n in left if init.get(n, 0.0) > 0] or [math.inf]
    )
    root = solve_for(sp.Eq(num / den, sp.Float(K)), "x", lo=0.0, hi=hi)

    result = {name: float(expr.subs(x, root)) for name, expr in conc.items()}
    result["x"] = root
    return result


def kp_from_kc(Kc: float, dn: int, T: float) -> float:  # noqa: N803
    """Kp = Kc (RT)^Δn — Δn counts gas moles only, products minus reactants."""
    return Kc * (R_ATM * T) ** dn


def kc_from_kp(Kp: float, dn: int, T: float) -> float:  # noqa: N803
    return Kp / (R_ATM * T) ** dn


def percent_dissoc(reacted: float, initial: float) -> float:
    return 100.0 * reacted / initial


def sig(value: float, digits: int = 3) -> float:
    """Round to significant figures the way the sheet's answers are written."""
    if value == 0:
        return 0.0
    return round(value, -int(math.floor(math.log10(abs(value)))) + (digits - 1))
