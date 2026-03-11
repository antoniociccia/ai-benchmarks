"""
11 Benchmark Tests — Hard, with automated validation.
Each test returns: { name, category, prompt, validate(response) -> {score, max_score, details} }
"""

import json
import re
import math

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict | list | None:
    """Try to extract JSON from a response, handling markdown fences."""
    if not text:
        return None
    # Try ```json ... ``` first
    m = re.search(r"```(?:json)?\s*\n?([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try raw JSON
    for start in ("{", "["):
        idx = text.find(start)
        if idx != -1:
            try:
                return json.loads(text[idx:])
            except json.JSONDecodeError:
                # Try to find matching bracket
                depth = 0
                end_char = "}" if start == "{" else "]"
                for i, c in enumerate(text[idx:], idx):
                    if c == start:
                        depth += 1
                    elif c == end_char:
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(text[idx:i+1])
                            except json.JSONDecodeError:
                                break
    return None


def _extract_code(text: str, lang: str = "python") -> str:
    """Extract code block from response, handling multiple fences and edge cases."""
    if not text:
        return ""
    # Try to find ALL code blocks and pick the longest (most likely the actual solution)
    blocks = re.findall(r"```(?:" + lang + r")?\s*\n([\s\S]*?)```", text)
    if blocks:
        # Return the longest block (usually the main solution, not a short snippet)
        return max(blocks, key=len).strip()
    # Fallback: try to find code without language tag
    blocks = re.findall(r"```\s*\n([\s\S]*?)```", text)
    if blocks:
        return max(blocks, key=len).strip()
    # Last resort: try the whole response, strip obvious prose lines
    lines = text.strip().split("\n")
    code_lines = []
    for l in lines:
        stripped = l.strip()
        # Skip lines that look like prose/markdown
        if stripped.startswith("```"):
            continue
        if stripped.startswith("#") and not stripped.startswith("# ") and len(stripped) > 2:
            # Likely a Python comment, keep it
            code_lines.append(l)
        elif re.match(r"^(def |class |import |from |if |for |while |return |    |$)", l):
            code_lines.append(l)
        elif not any(stripped.startswith(w) for w in ["Here", "This", "The ", "Note", "I ", "Let", "Below", "Above"]):
            code_lines.append(l)
    return "\n".join(code_lines)


def _safe_exec(code: str, test_code: str, timeout: int = 10) -> tuple[bool, str]:
    """Execute code + test_code safely, return (passed, output)."""
    if not code:
        return False, "no code to execute"
    import subprocess, tempfile, os
    full_code = code + "\n\n" + test_code
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(full_code)
        f.flush()
        try:
            result = subprocess.run(
                ["python3", f.name],
                capture_output=True, text=True, timeout=timeout
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, (result.stderr or result.stdout).strip()[-500:]
        except subprocess.TimeoutExpired:
            return False, "TIMEOUT"
        finally:
            os.unlink(f.name)


# ─────────────────────────────────────────────────────────────
# TEST 1: Multi-step Math & Combinatorics
# ─────────────────────────────────────────────────────────────

def test_math():
    prompt = """Solve this step by step. Give ONLY the final numerical answer on the last line, no text.

A company has 12 employees. They need to form 3 committees:
- Committee A: exactly 4 members
- Committee B: exactly 3 members
- Committee C: exactly 2 members

Rules:
1. No employee can be on more than one committee.
2. Employee #1 and Employee #2 MUST be on the same committee.
3. Employee #3 CANNOT be on Committee A.

How many valid ways can the committees be formed?
(The remaining 3 employees not on any committee are irrelevant.)
"""

    def validate(response: str) -> dict:
        """
        Exact combinatorial calculation:
        Employees #1 and #2 must be together. #3 cannot be on A.

        Case 1: #1,#2 on Committee A (size 4 → pick 2 more from remaining 10)
          - #3 cannot be on A, so pick 2 from {4..12} = 9 people → C(9,2) = 36
          - Committee B (size 3) from remaining 8 (including #3): C(8,3) = 56
          - Committee C (size 2) from remaining 5: C(5,2) = 10
          → 36 × 56 × 10 = 20160

        Case 2: #1,#2 on Committee B (size 3 → pick 1 more from remaining 10)
          - Pick 1 from 10: C(10,1) = 10
          - Committee A (size 4) from remaining 9, but #3 cannot be on A
            → If #3 was not picked for B: pick 4 from 8 non-#3 people = C(8,4) = 70
              remaining for C: C(5,2) = 10 → 70 × 10 = 700
              But wait—need to check if #3 was picked for B.
            → If #3 picked for B (1 way out of 10): A from remaining 9 (all allowed, no #3): C(9,4)=126, C from C(5,2)=10 → 126×10=1260
            → If #3 not picked for B (9 ways): A from remaining 9 minus #3 = 8: C(8,4)=70, C from C(5,2)=10 → 70×10=700
          → 1×1260 + 9×700 = 1260 + 6300 = 7560

        Case 3: #1,#2 on Committee C (size 2 → full, no more picks)
          - Committee A (size 4) from remaining 10, #3 cannot be on A
            → pick 4 from 9 (exclude #3): C(9,4) = 126
          - Committee B (size 3) from remaining 6 (including #3): C(6,3) = 20
          → 126 × 20 = 2520

        Total = 20160 + 7560 + 2520 = 30240
        """
        correct = 30240
        # Extract number from last line
        lines = [l.strip() for l in response.strip().split("\n") if l.strip()]
        score = 0
        found = None
        for line in reversed(lines):
            nums = re.findall(r"[\d,]+", line.replace(",", ""))
            if nums:
                try:
                    found = int(nums[-1].replace(",", ""))
                except ValueError:
                    continue
                break
        if found == correct:
            score = 10
        elif found and abs(found - correct) / correct < 0.01:
            score = 7
        elif found and abs(found - correct) / correct < 0.1:
            score = 3
        return {"score": score, "max_score": 10, "details": f"expected={correct}, got={found}"}

    return {
        "name": "Multi-step Combinatorics",
        "category": "math_logic",
        "prompt": prompt,
        "validate": validate,
    }


# ─────────────────────────────────────────────────────────────
# TEST 2: Algorithm Implementation (Hard)
# ─────────────────────────────────────────────────────────────

def test_code_generation():
    prompt = """Write a Python function `solve_n_queens(n: int) -> list[list[int]]` that returns ALL solutions to the N-Queens problem.

Each solution is a list of length n where solution[i] is the column index (0-based) of the queen in row i.

Requirements:
- Solutions must be sorted lexicographically.
- Must handle n up to 12 efficiently (under 5 seconds).
- Do NOT use any external libraries.

Return ONLY the Python code, no explanations."""

    test_code = """
# Validation
import time

# n=1
assert solve_n_queens(1) == [[0]]

# n=4: known 2 solutions
r4 = solve_n_queens(4)
assert len(r4) == 2, f"n=4: expected 2, got {len(r4)}"
assert r4 == [[1,3,0,2],[2,0,3,1]], f"n=4 wrong: {r4}"

# n=8: known 92 solutions
r8 = solve_n_queens(8)
assert len(r8) == 92, f"n=8: expected 92, got {len(r8)}"
assert r8 == sorted(r8), "n=8 not sorted"
# verify each is valid
for sol in r8:
    for i in range(8):
        for j in range(i+1,8):
            assert sol[i] != sol[j], "same column"
            assert abs(sol[i]-sol[j]) != abs(i-j), "diagonal"

# n=10: 724 solutions
r10 = solve_n_queens(10)
assert len(r10) == 724, f"n=10: expected 724, got {len(r10)}"

# n=12 perf test
t0 = time.time()
r12 = solve_n_queens(12)
elapsed = time.time() - t0
assert len(r12) == 14200, f"n=12: expected 14200, got {len(r12)}"
assert elapsed < 5, f"n=12 too slow: {elapsed:.2f}s"

print("ALL_TESTS_PASSED")
"""

    def validate(response: str) -> dict:
        code = _extract_code(response)
        passed, output = _safe_exec(code, test_code, timeout=15)
        if passed and "ALL_TESTS_PASSED" in output:
            return {"score": 10, "max_score": 10, "details": "all cases passed"}
        return {"score": 0, "max_score": 10, "details": f"failed: {output[:300]}"}

    return {
        "name": "N-Queens Solver",
        "category": "code_generation",
        "prompt": prompt,
        "validate": validate,
    }


# ─────────────────────────────────────────────────────────────
# TEST 3: Code Debugging (complex bug)
# ─────────────────────────────────────────────────────────────

def test_code_debugging():
    prompt = """The following Python function implements Dijkstra's shortest path algorithm but contains EXACTLY 3 bugs. Find and fix all 3 bugs.

```python
import heapq

def dijkstra(graph: dict[str, list[tuple[str, int]]], start: str, end: str) -> tuple[int, list[str]]:
    \"\"\"
    Returns (distance, path) from start to end.
    graph: adjacency list {node: [(neighbor, weight), ...]}
    Returns (float('inf'), []) if no path exists.
    \"\"\"
    distances = {node: float('inf') for node in graph}
    distances[start] = 0
    previous = {}
    pq = [(0, start)]
    visited = set()

    while pq:
        current_dist, current = heapq.heappop(pq)

        if current in visited:
            continue
        visited.add(current)

        if current == end:
            break

        for neighbor, weight in graph[current]:
            if neighbor in visited:
                continue
            new_dist = current_dist + weight
            if new_dist <= distances[neighbor]:  # BUG 1: should be < not <=
                distances[neighbor] = new_dist
                previous[neighbor] = current
                heapq.heappush(pq, (new_dist, neighbor))

    # Reconstruct path
    path = []
    current = end
    while current in previous:
        path.append(current)
        current = previous[current]
    path.append(start)  # BUG 2: appends start even if no path exists

    return distances[end], path  # BUG 3: path not reversed
```

Return the COMPLETE fixed function as Python code. No explanations needed."""

    test_code = """
# Test the fixed function
g1 = {
    'A': [('B', 1), ('C', 4)],
    'B': [('C', 2), ('D', 5)],
    'C': [('D', 1)],
    'D': []
}
dist, path = dijkstra(g1, 'A', 'D')
assert dist == 4, f"expected 4, got {dist}"
assert path == ['A', 'B', 'C', 'D'], f"expected ['A','B','C','D'], got {path}"

# No path
g2 = {
    'A': [('B', 1)],
    'B': [],
    'C': [('A', 1)]
}
dist2, path2 = dijkstra(g2, 'A', 'C')
assert dist2 == float('inf'), f"expected inf, got {dist2}"
assert path2 == [], f"expected [], got {path2}"

# Single node
g3 = {'A': []}
dist3, path3 = dijkstra(g3, 'A', 'A')
assert dist3 == 0, f"expected 0, got {dist3}"
assert path3 == ['A'], f"expected ['A'], got {path3}"

# Diamond with equal weights — must not duplicate via <=
g4 = {
    'A': [('B', 1), ('C', 1)],
    'B': [('D', 1)],
    'C': [('D', 1)],
    'D': []
}
dist4, path4 = dijkstra(g4, 'A', 'D')
assert dist4 == 2
assert len(path4) == 3  # A -> B/C -> D

print("ALL_TESTS_PASSED")
"""

    def validate(response: str) -> dict:
        code = _extract_code(response)
        # Ensure heapq is imported
        if "import heapq" not in code:
            code = "import heapq\n" + code
        passed, output = _safe_exec(code, test_code, timeout=10)
        if passed and "ALL_TESTS_PASSED" in output:
            return {"score": 10, "max_score": 10, "details": "all 3 bugs fixed"}
        # Partial credit: check which tests pass
        partial = 0
        for i, test_block in enumerate(test_code.split("\n\n# ")[1:], 1):
            p, _ = _safe_exec(code, test_block, timeout=5)
            if p:
                partial += 1
        score = min(7, partial * 2)  # max 7 for partial
        return {"score": score, "max_score": 10, "details": f"partial: {partial}/4 tests, output: {output[:200]}"}

    return {
        "name": "Dijkstra 3-Bug Fix",
        "category": "code_debugging",
        "prompt": prompt,
        "validate": validate,
    }


# ─────────────────────────────────────────────────────────────
# TEST 4: Constraint Satisfaction / Logic Puzzle
# ─────────────────────────────────────────────────────────────

def test_logic_puzzle():
    prompt = """Solve this logic puzzle. Give ONLY the final answer in the exact format specified at the end.

Five houses in a row (positions 1-5, left to right). Each has a different color, a different nationality owner, a different pet, a different drink, and a different hobby.

Clues:
1. The British person lives in the red house.
2. The Swedish person keeps dogs.
3. The Danish person drinks tea.
4. The green house is immediately to the left of the white house.
5. The green house owner drinks coffee.
6. The person who plays chess keeps birds.
7. The yellow house owner plays football.
8. The person in the middle house (position 3) drinks milk.
9. The Norwegian lives in the first house (position 1).
10. The person who plays baseball lives next to the cat owner.
11. The person who plays football lives next to the horse owner.
12. The person who plays tennis drinks beer.
13. The German plays hockey.
14. The Norwegian lives next to the blue house.
15. The person who plays baseball lives next to the water drinker.

Answer format (one line per house, tab-separated):
Position<TAB>Color<TAB>Nationality<TAB>Pet<TAB>Drink<TAB>Hobby
1<TAB>...<TAB>...<TAB>...<TAB>...<TAB>...
2<TAB>...<TAB>...<TAB>...<TAB>...<TAB>...
3<TAB>...<TAB>...<TAB>...<TAB>...<TAB>...
4<TAB>...<TAB>...<TAB>...<TAB>...<TAB>...
5<TAB>...<TAB>...<TAB>...<TAB>...<TAB>..."""

    # Known solution (Einstein's riddle)
    solution = {
        1: ("yellow", "norwegian", "cats", "water", "football"),
        2: ("blue", "danish", "horse", "tea", "baseball"),
        3: ("red", "british", "birds", "milk", "chess"),
        4: ("green", "german", "fish", "coffee", "hockey"),
        5: ("white", "swedish", "dogs", "beer", "tennis"),
    }

    def validate(response: str) -> dict:
        if not response:
            return {"score": 0, "max_score": 10, "details": "empty response"}
        score = 0
        details = []
        # Parse response — handle tabs, pipes, multiple spaces, markdown tables
        lines = response.strip().split("\n")
        parsed = {}
        for line in lines:
            # Strip markdown table formatting
            clean = line.strip().strip("|").strip()
            if not clean or clean.startswith("---") or clean.startswith("==="):
                continue
            # Normalize separators: tabs, pipes, 2+ spaces
            parts = re.split(r"\t+|\s{2,}|\|", clean)
            parts = [p.strip().lower() for p in parts if p.strip()]
            if not parts:
                continue
            # Try to find position number (could be "1", "1.", "House 1", etc.)
            pos = None
            start_idx = 0
            for pi, p in enumerate(parts):
                m = re.search(r"(\d)", p)
                if m:
                    candidate = int(m.group(1))
                    if 1 <= candidate <= 5:
                        pos = candidate
                        start_idx = pi + 1
                        break
            if pos is not None and len(parts) - start_idx >= 5:
                parsed[pos] = tuple(parts[start_idx:start_idx + 5])

        # Fallback: try to find solution values by scanning for known keywords
        if len(parsed) < 5:
            # Try line-by-line with more flexible patterns
            for line in lines:
                lower = line.lower()
                for pos in range(1, 6):
                    if str(pos) in line and pos not in parsed:
                        vals = []
                        for attr_set in [
                            ["yellow", "blue", "red", "green", "white"],
                            ["norwegian", "danish", "british", "german", "swedish"],
                            ["cats", "cat", "horse", "birds", "bird", "fish", "dogs", "dog"],
                            ["water", "tea", "milk", "coffee", "beer"],
                            ["football", "baseball", "chess", "hockey", "tennis"],
                        ]:
                            found = next((a for a in attr_set if a in lower), None)
                            if found:
                                vals.append(found)
                        if len(vals) == 5:
                            parsed[pos] = tuple(vals)
                            break

        if len(parsed) < 5:
            return {"score": 0, "max_score": 10, "details": f"could only parse {len(parsed)} houses"}

        correct_cells = 0
        total_cells = 25  # 5 houses × 5 attributes
        for pos in range(1, 6):
            if pos in parsed:
                for i, (got, expected) in enumerate(zip(parsed[pos], solution[pos])):
                    # Flexible matching
                    if expected in got or got in expected:
                        correct_cells += 1
                    else:
                        details.append(f"pos{pos}[{i}]: expected '{expected}', got '{got}'")

        if correct_cells == 25:
            score = 10
        elif correct_cells >= 20:
            score = 8
        elif correct_cells >= 15:
            score = 5
        elif correct_cells >= 10:
            score = 3
        else:
            score = 1

        return {"score": score, "max_score": 10,
                "details": f"{correct_cells}/25 cells correct. " + "; ".join(details[:5])}

    return {
        "name": "Einstein's Riddle (Extended)",
        "category": "logic_reasoning",
        "prompt": prompt,
        "validate": validate,
    }


# ─────────────────────────────────────────────────────────────
# TEST 5: Structured Data Extraction from Messy Text
# ─────────────────────────────────────────────────────────────

def test_data_extraction():
    prompt = """Extract structured data from this messy email chain. Return ONLY valid JSON, no commentary.

---BEGIN EMAIL CHAIN---
From: marco.rossi@acmecorp.it
To: sales-team@acmecorp.it
Date: 15 marzo 2025

Ragazzi, update veloce sui deal in pipeline:

1) **TechnoSoft SpA** — il CEO Luigi Bianchi mi ha confermato ieri al telefono che vogliono il pacchetto Enterprise (€45.000/anno). Closing previsto entro fine mese. Contatto tecnico: laura.verdi@technosoft.it, +39 02 5555 1234.

2) DataFlow srl: ancora in fase di valutazione. Budget dichiarato ~€12k annui, ma Maria Gonzalez (CTO) ha detto che potrebbe salire a 18k se includiamo il modulo analytics. Decision entro Q2. Tel. Maria: 333-9876543

3) PINNACLE GROUP LTD (UK) -> Grosso deal!! £120,000 per 3 anni (£40k/yr). John Smith, VP Engineering (j.smith@pinnacle.co.uk) sta spingendo internamente. Competitor: Salesforce. Need to send proposal by April 5th.

ps: Il deal con OmniTrade è saltato, budget tagliato. RIP.

---
Re: update pipeline
From: anna.ferrari@acmecorp.it
Date: 15 marzo 2025

Marco, aggiungo:
4) BioMed Research AG (Svizzera) - Dr. Hans Mueller, Chief Data Officer. Vogliono una POC di 3 mesi a CHF 8'500/mese (totale CHF 25'500). Se va bene passano a full license ~CHF 95'000/anno. Email: h.mueller@biomed-research.ch

Anche: per TechnoSoft ho sentito che il budget finale potrebbe essere €48.000 non €45.000 perchè aggiungono 5 utenze extra.

---END EMAIL CHAIN---

Extract to this EXACT JSON schema:
{
  "deals": [
    {
      "company": "string",
      "country": "string (IT/UK/CH/...)",
      "status": "active|evaluation|lost",
      "contacts": [{"name": "string", "role": "string", "email": "string|null", "phone": "string|null"}],
      "value": {"amount": number, "currency": "EUR|GBP|CHF", "period": "yearly|total|monthly"},
      "notes": "string (key details, max 50 words)",
      "deadline": "string|null (ISO date or quarter)"
    }
  ],
  "summary": {"total_active_deals": number, "total_pipeline_value_eur": number}
}

For pipeline value conversion use: 1 GBP = 1.17 EUR, 1 CHF = 1.04 EUR. Use the LATEST/corrected figures where applicable."""

    def validate(response: str) -> dict:
        data = _extract_json(response)
        if not data or "deals" not in data:
            return {"score": 0, "max_score": 10, "details": "no valid JSON with 'deals' key"}

        score = 0
        details = []
        deals = data["deals"]

        # Check we have right number of deals
        company_names = [d.get("company", "").lower() for d in deals]
        expected_companies = ["technosoft", "dataflow", "pinnacle", "biomed"]
        for ec in expected_companies:
            if any(ec in cn for cn in company_names):
                score += 0.5
            else:
                details.append(f"missing company containing '{ec}'")

        # Check OmniTrade is either absent or marked as lost
        omni = [d for d in deals if "omni" in d.get("company", "").lower()]
        if not omni:
            score += 0.5  # correctly excluded
        elif omni[0].get("status") == "lost":
            score += 0.5  # correctly marked lost

        # Check TechnoSoft updated value (€48k not €45k)
        ts = [d for d in deals if "techno" in d.get("company", "").lower()]
        if ts:
            val = ts[0].get("value", {})
            amt = val.get("amount", 0)
            if amt == 48000:
                score += 1.5  # caught the correction
                details.append("correctly updated TechnoSoft to 48k")
            elif amt == 45000:
                score += 0.5
                details.append("TechnoSoft: used original 45k, missed correction to 48k")

        # Check Pinnacle value and currency
        pin = [d for d in deals if "pinnacle" in d.get("company", "").lower()]
        if pin:
            val = pin[0].get("value", {})
            if val.get("currency") == "GBP":
                score += 0.5
            if val.get("amount") in (120000, 40000):
                score += 0.5
            if pin[0].get("country", "").upper() in ("UK", "GB"):
                score += 0.5

        # Check BioMed
        bm = [d for d in deals if "biomed" in d.get("company", "").lower() or "bio" in d.get("company", "").lower()]
        if bm:
            val = bm[0].get("value", {})
            if val.get("currency") == "CHF":
                score += 0.5
            if bm[0].get("country", "").upper() in ("CH", "SVIZZERA", "SWITZERLAND"):
                score += 0.5

        # Check contacts have emails/phones
        total_contacts = sum(len(d.get("contacts", [])) for d in deals)
        if total_contacts >= 4:
            score += 1
        elif total_contacts >= 2:
            score += 0.5

        # Check summary
        summary = data.get("summary", {})
        active = summary.get("total_active_deals", 0)
        if active in (3, 4):  # 3 active + 1 evaluation, or 4 if counting evaluation
            score += 0.5

        # Pipeline value check (approximate)
        # TechnoSoft: €48k, DataFlow: ~€18k, Pinnacle: £120k=€140.4k or £40k/yr=€46.8k, BioMed: CHF25.5k=€26.52k or CHF95k=€98.8k
        pipeline_eur = summary.get("total_pipeline_value_eur", 0)
        if pipeline_eur > 0:
            score += 1  # at least attempted
            if 100000 < pipeline_eur < 350000:
                score += 0.5  # reasonable range
            details.append(f"pipeline_eur={pipeline_eur}")

        # Check JSON schema compliance
        schema_ok = True
        for d in deals:
            if not all(k in d for k in ("company", "country", "status", "contacts", "value")):
                schema_ok = False
                break
        if schema_ok:
            score += 1

        score = min(10, round(score, 1))
        return {"score": score, "max_score": 10, "details": "; ".join(details) if details else "ok"}

    return {
        "name": "Messy Email → Structured JSON",
        "category": "data_extraction",
        "prompt": prompt,
        "validate": validate,
    }


# ─────────────────────────────────────────────────────────────
# TEST 6: Technical Translation IT↔EN with terminology
# ─────────────────────────────────────────────────────────────

def test_translation():
    prompt = """Translate the following Italian technical/legal text to English.
Maintain precise legal and financial terminology. Do NOT paraphrase — translate faithfully.
Return ONLY the English translation, no notes.

---
CLAUSOLA 7.3 — Limitazione di Responsabilità

Fermo restando quanto previsto dall'art. 1229 c.c., la responsabilità complessiva del Fornitore derivante da o in connessione con il presente Contratto, sia essa contrattuale, extracontrattuale (inclusa la negligenza), per violazione di obblighi di legge o a qualsiasi altro titolo, non potrà in alcun caso superare un importo pari al 150% dei corrispettivi effettivamente percepiti dal Fornitore nei 12 (dodici) mesi precedenti l'evento che ha dato origine alla pretesa risarcitoria.

Sono escluse dalla suddetta limitazione: (a) le ipotesi di dolo o colpa grave; (b) la violazione degli obblighi di riservatezza di cui all'art. 9; (c) la violazione dei diritti di proprietà intellettuale di terzi; (d) gli obblighi di indennizzo previsti dall'art. 11.2.

Il Fornitore non sarà in alcun caso responsabile per danni indiretti, incidentali, consequenziali, punitivi o per il mancato guadagno, la perdita di dati, l'interruzione dell'attività o la perdita di avviamento, anche qualora sia stato informato della possibilità del verificarsi di tali danni.
---"""

    key_terms = {
        # (italian concept -> required english terms, at least one must appear)
        "limitazione di responsabilità": ["limitation of liability", "liability limitation"],
        "art. 1229 c.c.": ["art. 1229", "article 1229", "civil code"],
        "contrattuale": ["contractual"],
        "extracontrattuale": ["extra-contractual", "extracontractual", "tortious", "tort"],
        "negligenza": ["negligence"],
        "150%": ["150%"],
        "corrispettivi": ["fees", "compensation", "consideration", "amounts"],
        "pretesa risarcitoria": ["claim", "damage claim", "compensation claim"],
        "dolo": ["willful misconduct", "fraud", "intentional", "wilful"],
        "colpa grave": ["gross negligence", "gross fault"],
        "riservatezza": ["confidentiality"],
        "proprietà intellettuale": ["intellectual property"],
        "indennizzo": ["indemnif", "indemnity", "indemnification"],
        "danni indiretti": ["indirect damage", "indirect damages", "indirect losses", "indirect loss"],
        "consequenziali": ["consequential"],
        "punitivi": ["punitive"],
        "mancato guadagno": ["lost profit", "loss of profit", "lost earnings", "loss of earnings"],
        "perdita di dati": ["loss of data", "data loss"],
        "avviamento": ["goodwill"],
    }

    def validate(response: str) -> dict:
        text = response.lower()
        matched = 0
        missed = []
        for it_term, en_options in key_terms.items():
            if any(opt.lower() in text for opt in en_options):
                matched += 1
            else:
                missed.append(it_term)
        total = len(key_terms)
        ratio = matched / total
        if ratio >= 0.95:
            score = 10
        elif ratio >= 0.85:
            score = 8
        elif ratio >= 0.7:
            score = 6
        elif ratio >= 0.5:
            score = 4
        else:
            score = 2
        return {"score": score, "max_score": 10,
                "details": f"{matched}/{total} terms matched. Missed: {missed[:5]}"}

    return {
        "name": "Legal IT→EN Translation",
        "category": "translation",
        "prompt": prompt,
        "validate": validate,
    }


# ─────────────────────────────────────────────────────────────
# TEST 7: Creative Writing with Hard Constraints
# ─────────────────────────────────────────────────────────────

def test_creative_writing():
    prompt = """Write a short story (exactly 150-200 words) that satisfies ALL these constraints:

1. Set in a library at midnight
2. Contains exactly 3 characters (no more, no less)
3. Includes a plot twist in the final paragraph
4. Every paragraph must start with a different vowel (A, E, I, O, U) — exactly 5 paragraphs
5. Must contain at least one line of dialogue per character (3 distinct speakers)
6. The word "silence" must appear exactly twice
7. Title must be an oxymoron (two contradictory words)
8. No sentence longer than 20 words
9. Must include one metaphor and one simile (clearly identifiable)

Return the story with the title on the first line."""

    def validate(response: str) -> dict:
        score = 0
        details = []
        lines = response.strip().split("\n")
        title = lines[0].strip().strip("#").strip("*").strip()
        body = "\n".join(lines[1:]).strip()

        # 1. Word count (150-200)
        words = body.split()
        wc = len(words)
        if 150 <= wc <= 200:
            score += 1
            details.append(f"word count {wc} ✓")
        elif 130 <= wc <= 220:
            score += 0.5
            details.append(f"word count {wc} (close)")
        else:
            details.append(f"word count {wc} ✗")

        # 4. Five paragraphs starting with vowels A, E, I, O, U
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        # Also try single newline if double didn't work
        if len(paragraphs) < 4:
            paragraphs = [p.strip() for p in body.split("\n") if p.strip() and len(p.strip()) > 20]
        if len(paragraphs) == 5:
            score += 1
            details.append("5 paragraphs ✓")
            vowels_used = []
            for p in paragraphs:
                first_letter = p.lstrip('"\'""''«»— ')[0].upper() if p else ""
                vowels_used.append(first_letter)
            if all(v in "AEIOU" for v in vowels_used) and len(set(vowels_used)) == 5:
                score += 1.5
                details.append(f"vowel starts {vowels_used} ✓")
            else:
                details.append(f"vowel starts {vowels_used} ✗")
        else:
            details.append(f"paragraphs: {len(paragraphs)} ✗")

        # 5. Three distinct speakers (dialogue)
        dialogue_marks = re.findall(r'[""«](.*?)[""»]|"(.*?)"', body)
        # Count lines with speech verbs or quotes
        dialogue_lines = re.findall(r'"[^"]+"|"[^"]+"|«[^»]+»', body)
        if len(dialogue_lines) >= 3:
            score += 1.5
            details.append(f"dialogue lines: {len(dialogue_lines)} ✓")
        else:
            details.append(f"dialogue lines: {len(dialogue_lines)} ✗")

        # 6. "silence" appears exactly twice
        silence_count = body.lower().split("silence").__len__() - 1
        if silence_count == 2:
            score += 1.5
            details.append("'silence' ×2 ✓")
        else:
            details.append(f"'silence' ×{silence_count} ✗")

        # 7. Title is oxymoron (hard to auto-check, give credit if 2+ words)
        title_words = title.split()
        if len(title_words) >= 2:
            score += 0.5
            details.append(f"title '{title}' (2+ words)")

        # 8. No sentence > 20 words
        sentences = re.split(r'[.!?]+', body)
        long_sentences = [s for s in sentences if len(s.split()) > 20]
        if not long_sentences:
            score += 1
            details.append("all sentences ≤20 words ✓")
        else:
            details.append(f"{len(long_sentences)} sentences >20 words ✗")

        # 1 (library at midnight) — check keywords
        if any(w in body.lower() for w in ["library", "libreria"]):
            score += 0.5
        if any(w in body.lower() for w in ["midnight", "mezzanotte"]):
            score += 0.5

        # 2. Exactly 3 characters — hard to auto-validate, give partial credit
        # Check for 3+ proper nouns or character names
        score += 0.5  # benefit of the doubt

        score = min(10, round(score, 1))
        return {"score": score, "max_score": 10, "details": "; ".join(details)}

    return {
        "name": "Constrained Creative Writing",
        "category": "creative_writing",
        "prompt": prompt,
        "validate": validate,
    }


# ─────────────────────────────────────────────────────────────
# TEST 8: Strict Instruction Following
# ─────────────────────────────────────────────────────────────

def test_instruction_following():
    prompt = """Follow these instructions EXACTLY. Any deviation = failure.

1. Output exactly 7 lines (not counting blank lines).
2. Line 1: The word "BEGIN" followed by today's day of the week in uppercase (e.g., "BEGIN MONDAY")
3. Line 2: The numbers 1 through 10, separated by pipes (|), in REVERSE order.
4. Line 3: The sentence "The quick brown fox" with every other word in UPPERCASE starting with the first word. (i.e., word1=upper, word2=lower, word3=upper, word4=lower)
5. Line 4: A valid IPv4 address where all four octets are prime numbers and their sum equals 100.
6. Line 5: The NATO phonetic alphabet for the letters in "BENCHMARK" (space-separated).
7. Line 6: The number 2^64 written out with digit grouping using commas (e.g., 1,234,567).
8. Line 7: The word "END" followed by the MD5 hash of the string "benchmark2025" (lowercase hex).

Output ONLY these 7 lines. No headers, no explanations, no blank lines between them."""

    def validate(response: str) -> dict:
        lines = [l for l in response.strip().split("\n") if l.strip()]
        score = 0
        details = []

        # Line count
        if len(lines) == 7:
            score += 1
            details.append("7 lines ✓")
        else:
            details.append(f"{len(lines)} lines ✗")
            # Pad or trim for further checks
            while len(lines) < 7:
                lines.append("")

        # Line 1: BEGIN + day of week
        days = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
        l1 = lines[0].strip().upper()
        if l1.startswith("BEGIN") and any(d in l1 for d in days):
            score += 1
            details.append("line1 ✓")

        # Line 2: 10|9|8|...|1
        expected_l2 = "10|9|8|7|6|5|4|3|2|1"
        l2 = lines[1].strip().replace(" ", "")
        if l2 == expected_l2:
            score += 1
            details.append("line2 ✓")
        else:
            details.append(f"line2: got '{lines[1].strip()}'")

        # Line 3: THE quick BROWN fox
        l3 = lines[2].strip()
        expected_l3 = "THE quick BROWN fox"
        if l3 == expected_l3:
            score += 1.5
            details.append("line3 ✓")
        else:
            details.append(f"line3: got '{l3}'")

        # Line 4: IPv4, all octets prime, sum = 100
        l4 = lines[3].strip()
        ip_match = re.match(r"(\d+)\.(\d+)\.(\d+)\.(\d+)", l4)
        if ip_match:
            octets = [int(x) for x in ip_match.groups()]
            def is_prime(n):
                if n < 2: return False
                for i in range(2, int(n**0.5)+1):
                    if n % i == 0: return False
                return True
            all_prime = all(is_prime(o) and 0 <= o <= 255 for o in octets)
            if all_prime and sum(octets) == 100:
                score += 1.5
                details.append(f"line4 {l4} ✓")
            else:
                details.append(f"line4: primes={all_prime}, sum={sum(octets)}")
        else:
            details.append(f"line4: no IP found")

        # Line 5: NATO for BENCHMARK
        nato = {
            "B": "BRAVO", "E": "ECHO", "N": "NOVEMBER", "C": "CHARLIE",
            "H": "HOTEL", "M": "MIKE", "A": "ALPHA", "R": "ROMEO", "K": "KILO"
        }
        expected_nato = " ".join(nato[c] for c in "BENCHMARK")
        l5 = lines[4].strip().upper()
        if l5 == expected_nato.upper():
            score += 1.5
            details.append("line5 ✓")
        else:
            # Partial credit
            expected_words = expected_nato.upper().split()
            got_words = l5.split()
            matching = sum(1 for a, b in zip(expected_words, got_words) if a == b)
            if matching >= 7:
                score += 1
            details.append(f"line5: got '{l5[:60]}'")

        # Line 6: 2^64 with commas
        val_2_64 = 2**64  # 18446744073709551616
        expected_l6 = f"{val_2_64:,}"
        l6 = lines[5].strip()
        if l6 == expected_l6:
            score += 1
            details.append("line6 ✓")
        else:
            # Check if the number is correct but formatting differs
            if l6.replace(",", "").replace(".", "").replace(" ", "") == str(val_2_64):
                score += 0.5
            details.append(f"line6: expected '{expected_l6}', got '{l6}'")

        # Line 7: END + MD5 of "benchmark2025"
        import hashlib
        expected_hash = hashlib.md5("benchmark2025".encode()).hexdigest()
        l7 = lines[6].strip()
        if l7.startswith("END") and expected_hash in l7.lower():
            score += 1.5
            details.append("line7 ✓")
        else:
            details.append(f"line7: expected hash {expected_hash}")

        score = min(10, round(score, 1))
        return {"score": score, "max_score": 10, "details": "; ".join(details)}

    return {
        "name": "Exact Instruction Following",
        "category": "instruction_following",
        "prompt": prompt,
        "validate": validate,
    }


# ─────────────────────────────────────────────────────────────
# TEST 9: Advanced Factual Knowledge
# ─────────────────────────────────────────────────────────────

def test_knowledge():
    prompt = """Answer these 10 questions. Give ONLY the answer for each, numbered 1-10. Be precise.

1. What is the exact distance in km from Earth to the Moon at perigee (closest approach)? Round to nearest 1000 km.
2. In what year was the P vs NP problem formally stated by Stephen Cook?
3. What is the chemical formula of the mineral Beryl?
4. Who proved the Poincaré conjecture, and in what year was the proof accepted?
5. What is the orbital period of Jupiter in Earth years? Round to 1 decimal.
6. In computing, what is the exact value of 2^128 in decimal?
7. What enzyme catalyzes the first committed step of glycolysis?
8. What is the ISO 639-1 code for the Basque language?
9. In which year did the Byzantine Empire definitively fall (conquest of Constantinople)?
10. What is the Schwarzschild radius formula? Express using G, M, and c."""

    answers = {
        1: {"accept": ["356000", "356,000", "356500", "356,500"], "partial": ["357000", "357,000", "363000", "363,000"]},
        2: {"accept": ["1971"], "partial": ["1970", "1972"]},
        3: {"accept": ["be3al2si6o18", "be3al2(sio3)6", "be₃al₂si₆o₁₈", "be3al2(si6o18)"], "partial": []},
        4: {"accept": ["perelman"], "partial": ["grigori"]},  # Year: 2003 (proof) or 2006 (accepted)
        5: {"accept": ["11.9", "11.86"], "partial": ["11.8", "12.0", "12"]},
        6: {"accept": ["340282366920938463463374607431768211456"], "partial": []},
        7: {"accept": ["phosphofructokinase", "pfk", "pfk-1", "phosphofructokinase-1"], "partial": ["hexokinase"]},
        8: {"accept": ["eu"], "partial": []},
        9: {"accept": ["1453"], "partial": []},
        10: {"accept": ["2gm/c"], "partial": ["r=2gm", "schwarzschild"]},
    }

    def validate(response: str) -> dict:
        score = 0
        details = []
        text = response.lower().replace(" ", "")
        lines = response.strip().split("\n")

        for qnum, checks in answers.items():
            # Find the line for this question
            answer_text = ""
            for line in lines:
                if line.strip().startswith(f"{qnum}.") or line.strip().startswith(f"{qnum})"):
                    answer_text = line.lower().replace(" ", "").replace(",", "")
                    break
            if not answer_text:
                # Try to find it anywhere
                answer_text = text

            found = False
            for acc in checks["accept"]:
                if acc.lower().replace(" ", "").replace(",", "") in answer_text:
                    score += 1
                    found = True
                    break
            if not found:
                for par in checks.get("partial", []):
                    if par.lower().replace(" ", "") in answer_text:
                        score += 0.5
                        found = True
                        details.append(f"Q{qnum}: partial")
                        break
            if not found:
                details.append(f"Q{qnum}: wrong")

        score = min(10, round(score, 1))
        return {"score": score, "max_score": 10, "details": "; ".join(details)}

    return {
        "name": "Advanced Factual Knowledge",
        "category": "knowledge",
        "prompt": prompt,
        "validate": validate,
    }


# ─────────────────────────────────────────────────────────────
# TEST 10: Code Optimization Challenge
# ─────────────────────────────────────────────────────────────

def test_code_optimization():
    prompt = """Optimize this slow Python function. It computes the number of distinct subsequences of string `s` that equal string `t`.

The current brute-force implementation is O(2^n) and times out for inputs of length 30+.
Make it run in O(n*m) time and O(m) space where n=len(s), m=len(t).

```python
def num_distinct(s: str, t: str) -> int:
    \"\"\"Count distinct subsequences of s that equal t.\"\"\"
    if not t:
        return 1
    if not s:
        return 0
    count = 0
    if s[0] == t[0]:
        count += num_distinct(s[1:], t[1:])
    count += num_distinct(s[1:], t)
    return count
```

Return ONLY the optimized Python function. Must still be named `num_distinct` with same signature."""

    test_code = """
import time

# Correctness tests
assert num_distinct("rabbbit", "rabbit") == 3
assert num_distinct("babgbag", "bag") == 5
assert num_distinct("aaa", "a") == 3
assert num_distinct("aaa", "aa") == 3
assert num_distinct("", "a") == 0
assert num_distinct("a", "") == 1
assert num_distinct("aabdbaabeeadcbbdedacbbeecbabebaeeecaeabaedadcbdbcdaabebdadbbaeabdadeaabbabbecebbebcaddaacccebeaeedababedeacdeaaaeeaecbe",
                    "bddabdcae") == 10582116

# Performance test
t0 = time.time()
s_long = "aabb" * 25  # length 100
t_long = "ab" * 10     # length 20
result = num_distinct(s_long, t_long)
elapsed = time.time() - t0
assert elapsed < 1.0, f"Too slow: {elapsed:.2f}s"
assert result > 0

# Larger performance test
t0 = time.time()
result2 = num_distinct("a" * 1000, "a" * 100)
elapsed2 = time.time() - t0
assert elapsed2 < 2.0, f"Large test too slow: {elapsed2:.2f}s"

print("ALL_TESTS_PASSED")
"""

    def validate(response: str) -> dict:
        code = _extract_code(response)
        passed, output = _safe_exec(code, test_code, timeout=15)
        if passed and "ALL_TESTS_PASSED" in output:
            return {"score": 10, "max_score": 10, "details": "correct + fast"}
        # Partial: check if at least correct (ignoring perf)
        basic_test = """
assert num_distinct("rabbbit", "rabbit") == 3
assert num_distinct("babgbag", "bag") == 5
assert num_distinct("aaa", "a") == 3
assert num_distinct("", "a") == 0
assert num_distinct("a", "") == 1
print("BASIC_PASSED")
"""
        p2, o2 = _safe_exec(code, basic_test, timeout=10)
        if p2 and "BASIC_PASSED" in o2:
            return {"score": 5, "max_score": 10, "details": f"correct but slow/failed perf: {output[:200]}"}
        return {"score": 0, "max_score": 10, "details": f"failed: {output[:300]}"}

    return {
        "name": "DP Optimization Challenge",
        "category": "code_optimization",
        "prompt": prompt,
        "validate": validate,
    }


# ─────────────────────────────────────────────────────────────
# TEST 11: AGI — Autonomous Discovery & Self-Verification
# ─────────────────────────────────────────────────────────────

def test_agi_discovery():
    prompt = """You are faced with a novel, unpublished problem. No solution exists in any literature.
You must: (A) solve it, (B) write Python code that VERIFIES your solution, (C) write Python code that PROVES optimality.

## Problem: K-Harmonic Graph Coloring

Given a graph G and an integer K, a **K-harmonic coloring** is an assignment of colors from {1, 2, ..., K} to each vertex such that:

1. **Proper coloring**: No two adjacent vertices share the same color.
2. **Harmonic constraint**: For every vertex v, the SUM of the colors of all neighbors of v must be divisible by the color of v.
3. **Minimum sum**: Among all valid colorings, the total sum of all vertex colors is minimized.

### Instance

Graph with 10 vertices (0-9) and these edges:
(0,1),(0,2),(0,3),(1,2),(1,4),(1,5),(2,3),(2,6),(3,5),(3,7),(4,5),(4,8),(5,6),(5,9),(6,7),(6,9),(7,8),(7,9),(8,9)

K = 4 (colors available: 1, 2, 3, 4)

Adjacency list:
  Node 0: neighbors [1, 2, 3]       (degree 3)
  Node 1: neighbors [0, 2, 4, 5]    (degree 4)
  Node 2: neighbors [0, 1, 3, 6]    (degree 4)
  Node 3: neighbors [0, 2, 5, 7]    (degree 4)
  Node 4: neighbors [1, 5, 8]       (degree 3)
  Node 5: neighbors [1, 3, 4, 6, 9] (degree 5)
  Node 6: neighbors [2, 5, 7, 9]    (degree 4)
  Node 7: neighbors [3, 6, 8, 9]    (degree 4)
  Node 8: neighbors [4, 7, 9]       (degree 3)
  Node 9: neighbors [5, 6, 7, 8]    (degree 4)

### Required output format

```
SOLUTION: [c0, c1, c2, c3, c4, c5, c6, c7, c8, c9]
MINIMUM_SUM: <number>
```

Then provide a SINGLE Python code block that:
1. Defines the graph and your proposed coloring
2. Verifies ALL three constraints (proper, harmonic, sum)
3. Exhaustively searches the ENTIRE space (4^10 = 1,048,576 combinations) to PROVE no valid coloring has a lower sum
4. Prints "VERIFIED" if the coloring is valid
5. Prints "OPTIMAL" if no better coloring exists
6. Prints "FAILED" otherwise

Your code must complete in under 60 seconds."""

    # Pre-computed: UNIQUE optimal solution
    OPTIMAL_COLORING = [1, 3, 2, 3, 1, 2, 3, 1, 2, 4]
    OPTIMAL_SUM = 22
    EDGES = [(0,1),(0,2),(0,3),(1,2),(1,4),(1,5),(2,3),(2,6),(3,5),(3,7),
             (4,5),(4,8),(5,6),(5,9),(6,7),(6,9),(7,8),(7,9),(8,9)]
    N = 10
    K = 4

    def _build_adj(edges, n):
        adj = [[] for _ in range(n)]
        for u, v in edges:
            adj[u].append(v)
            adj[v].append(u)
        return adj

    def _is_valid_harmonic(coloring, edges, adj):
        """Check proper + harmonic."""
        for u, v in edges:
            if coloring[u] == coloring[v]:
                return False
        for v in range(len(coloring)):
            ns = sum(coloring[u] for u in adj[v])
            if ns % coloring[v] != 0:
                return False
        return True

    def validate(response: str) -> dict:
        if not response:
            return {"score": 0, "max_score": 10, "details": "empty response"}
        score = 0
        details = []
        adj = _build_adj(EDGES, N)

        # ── Part A: Extract proposed solution ──
        # Try multiple patterns: SOLUTION: [...], coloring = [...], [1, 3, ...] etc.
        proposed = None
        proposed_sum = None

        # Pattern 1: SOLUTION: [...]
        sol_match = re.search(r"SOLUTION:\s*\[([0-9,\s]+)\]", response)
        if sol_match:
            try:
                proposed = [int(x.strip()) for x in sol_match.group(1).split(",")]
            except ValueError:
                pass

        # Pattern 2: any list assignment like coloring = [...] or result = [...]
        if not proposed:
            for pat in [
                r"coloring\s*=\s*\[([0-9,\s]+)\]",
                r"optimal.*?\[([0-9,\s]+)\]",
                r"answer.*?\[([0-9,\s]+)\]",
            ]:
                m = re.search(pat, response, re.IGNORECASE)
                if m:
                    try:
                        candidate = [int(x.strip()) for x in m.group(1).split(",")]
                        if len(candidate) == N and all(1 <= c <= K for c in candidate):
                            proposed = candidate
                            break
                    except ValueError:
                        pass

        # Pattern 3: find any 10-element list with values 1-4
        if not proposed:
            for m in re.finditer(r"\[([0-9,\s]+)\]", response):
                try:
                    candidate = [int(x.strip()) for x in m.group(1).split(",")]
                    if len(candidate) == N and all(1 <= c <= K for c in candidate):
                        proposed = candidate
                        break
                except ValueError:
                    pass

        # Extract MINIMUM_SUM
        sum_match = re.search(r"MINIMUM_SUM:\s*(\d+)", response)
        if sum_match:
            try:
                proposed_sum = int(sum_match.group(1))
            except ValueError:
                pass
        # Also try "minimum sum is X" or "sum = X"
        if proposed_sum is None:
            m = re.search(r"(?:minimum|optimal|total)\s*sum[:\s=]*(\d+)", response, re.IGNORECASE)
            if m:
                proposed_sum = int(m.group(1))

        # Score: correct solution found
        if proposed and len(proposed) == N:
            if proposed == OPTIMAL_COLORING:
                score += 4  # exact match
                details.append("exact optimal coloring found")
            elif _is_valid_harmonic(proposed, EDGES, adj):
                s = sum(proposed)
                if s == OPTIMAL_SUM:
                    score += 4  # different but equally optimal (shouldn't happen — unique)
                    details.append(f"valid coloring, sum={s} (optimal)")
                else:
                    score += 2  # valid but not optimal
                    details.append(f"valid coloring, sum={s} (optimal is {OPTIMAL_SUM})")
            else:
                # Check which constraints fail
                proper_fail = any(proposed[u] == proposed[v] for u, v in EDGES)
                harm_fail = False
                for v in range(N):
                    ns = sum(proposed[u] for u in adj[v])
                    if ns % proposed[v] != 0:
                        harm_fail = True
                        break
                if proper_fail:
                    details.append("coloring not proper")
                if harm_fail:
                    details.append("harmonic constraint violated")
                score += 0
        else:
            details.append("could not parse solution")

        if proposed_sum == OPTIMAL_SUM:
            score += 1
            details.append("correct minimum sum")

        # ── Part B+C: Extract and run verification code ──
        code = _extract_code(response)
        if len(code) > 50:  # non-trivial code
            passed, output = _safe_exec(code, "", timeout=120)
            if passed:
                if "VERIFIED" in output and "OPTIMAL" in output:
                    score += 5  # full self-verification + optimality proof
                    details.append("code verifies + proves optimality")
                    # Bonus: if text solution was wrong but code found the right one,
                    # the model still demonstrated autonomous discovery
                    if proposed is None or proposed != OPTIMAL_COLORING:
                        score += 1  # bonus for code self-correcting
                        details.append("code autonomously found correct solution despite text error")
                elif "VERIFIED" in output:
                    score += 3  # verified but didn't prove optimality
                    details.append("code verifies but doesn't prove optimality")
                elif "OPTIMAL" in output:
                    score += 2
                    details.append("code claims optimal but doesn't verify")
                else:
                    score += 0.5  # code runs but no confirmation
                    details.append(f"code ran but output: {output[:100]}")
            else:
                details.append(f"code failed: {output[:200]}")
        else:
            details.append("no verification code found")

        score = min(10, round(score, 1))
        return {"score": score, "max_score": 10, "details": "; ".join(details)}

    return {
        "name": "AGI: K-Harmonic Graph Coloring (Novel Problem)",
        "category": "agi_discovery",
        "prompt": prompt,
        "validate": validate,
    }


# ─────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────

ALL_TESTS = [
    test_math,
    test_code_generation,
    test_code_debugging,
    test_logic_puzzle,
    test_data_extraction,
    test_translation,
    test_creative_writing,
    test_instruction_following,
    test_knowledge,
    test_code_optimization,
    test_agi_discovery,
]

def get_all_tests() -> list[dict]:
    """Return all test definitions."""
    return [t() for t in ALL_TESTS]
