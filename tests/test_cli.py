"""End-to-end CLI runs for the three target questions against the offline fake API."""

import json

import pytest
from pypdf import PdfReader

import fake_api
import wi
import wiki_api


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(wiki_api, "http_get_json", fake_api.http_get_json)
    monkeypatch.setattr(wi, "OUT_DIR", tmp_path / "out")
    monkeypatch.setenv("WI_SYNTHETIC", "1")


def run(capsys, *args):
    with pytest.raises(SystemExit) as e:
        wi.main(list(args))
    out = json.loads(capsys.readouterr().out)
    return e.value.code, out


def test_q1_fasting_pl_vs_cs(capsys):
    code, out = run(capsys, "analyze", "--topic", "Intermittent fasting", "--langs", "pl,cs", "--months", "24")
    assert code == 0
    assert out["results"]["pl"]["verdict"] == "growing"
    assert out["results"]["cs"]["verdict"] == "stable_or_unclear"
    assert out["ranking"][0]["lang"] == "pl"
    assert len(json.dumps(out, ensure_ascii=False).encode()) < 4000  # compact for small models
    assert len(PdfReader(out["files"]["pdf"]).pages) >= 2  # made by default, without --pdf: summary + appendix


def test_no_pdf_skips_the_report(capsys):
    code, out = run(capsys, "analyze", "--topic", "Intermittent fasting", "--langs", "pl,cs", "--no-pdf")
    assert code == 0 and "pdf" not in out["files"] and "chart_png" in out["files"]


def test_english_pdf_with_out_lang_en(capsys):
    code, out = run(
        capsys, "analyze", "--topic", "Intermittent fasting", "--langs", "pl,cs", "--out-lang", "en", "--question", "Q?"
    )
    text = PdfReader(out["files"]["pdf"]).pages[0].extract_text()
    assert code == 0 and "Conclusion" in text and "limitations" in text and "SYNTHETIC" in text
    assert not any("\u0400" <= ch <= "\u04ff" for ch in text)  # no Ukrainian left in the English report
    # re-rendering keeps the run's language unless overridden
    _, rep = run(capsys, "report", "--run-id", out["run_id"], "--conclusion", "Agent conclusion.")
    assert "Conclusion" in PdfReader(rep["files"]["pdf"]).pages[0].extract_text()
    _, rep = run(capsys, "report", "--run-id", out["run_id"], "--out-lang", "uk")
    assert "Висновок" in PdfReader(rep["files"]["pdf"]).pages[0].extract_text()


def test_q2_astronomy_uk_trust(capsys):
    code, out = run(
        capsys,
        "analyze",
        "--topic",
        "Astronomy",
        "--topic",
        "Solar System",
        "--topic",
        "Telescope",
        "--langs",
        "uk",
        "--months",
        "36",
    )
    r = out["results"]["uk"]
    assert code == 0
    assert r["yoy_raw"] > 0 > r["yoy_norm"]  # raw growth is explained by wiki-wide growth
    assert "PROJECT_SHIFT" in r["flags"] and r["confidence"] != "high"


def test_q3_english_ranking_with_pdf(capsys):
    code, out = run(
        capsys,
        "analyze",
        "--topic",
        "English language",
        "--topic",
        "International English Language Testing System",
        "--topic",
        "Test of English as a Foreign Language",
        "--langs",
        "uk,pl,tr,vi,id,pt",
        "--months",
        "24",
        "--pdf",
        "--question",
        "Інтерес до вивчення англійської: які аудиторії досліджувати далі?",
    )
    assert code == 0
    assert "MISSING_ARTICLE" in out["results"]["id"]["flags"]
    assert "SPIKE_DRIVEN" in out["results"]["vi"]["flags"]
    assert out["results"]["pt"]["verdict"] == "declining"
    assert {r["lang"] for r in out["ranking"][-2:]} == {"pt", "uk"}  # both lose share of interest
    pdf = PdfReader(out["files"]["pdf"])
    text = pdf.pages[0].extract_text()
    assert "СИНТЕТИЧНІ" in text and "Висновок" in text  # page 1 is the one-page summary
    appendix = "".join(pg.extract_text() for pg in pdf.pages[1:])
    assert "Додаток" in appendix and "Рейтинг" in appendix and "Місяць" in appendix
    assert "Немає в розділі: International English Language" in appendix  # id lacks IELTS
    assert f"с. {len(pdf.pages)} з {len(pdf.pages)}" in pdf.pages[-1].extract_text()


def test_report_rerender_with_agent_conclusion(capsys):
    _, out = run(capsys, "analyze", "--topic", "Intermittent fasting", "--langs", "pl,cs")
    code, rep = run(capsys, "report", "--run-id", out["run_id"], "--conclusion", "Тестовий висновок агента.")
    assert code == 0 and "Тестовий висновок агента." in PdfReader(rep["files"]["pdf"]).pages[0].extract_text()


def test_language_without_any_article(capsys):
    code, out = run(capsys, "analyze", "--topic", "Intermittent fasting", "--langs", "pl,tr")
    assert out["results"]["tr"]["status"] == "no_data"
    assert out["results"]["pl"]["verdict"] == "growing"


@pytest.mark.parametrize(
    "args,needle",
    [
        (["analyze", "--topic", "No such article xyz", "--langs", "pl"], "not found"),
        (["analyze", "--topic", "Astronomy", "--langs", "pl,???"], "unknown language"),
        (["analyze", "--langs", "pl"], "bad arguments"),
    ],
)
def test_errors_are_json_with_fix(capsys, args, needle):
    code, out = run(capsys, *args)
    assert code == 1 and needle in out["error"] and out["fix"]


def test_hyphenated_language_code_resolves(capsys):
    code, out = run(capsys, "analyze", "--topic", "Astronomy", "--langs", "zh-yue")
    assert code == 0 and out["results"]["zh-yue"].get("status") != "no_data"


def test_pdf_request_without_any_data_warns(capsys):
    code, out = run(capsys, "analyze", "--topic", "Intermittent fasting", "--langs", "tr", "--pdf")
    assert code == 0 and "pdf" not in out["files"]
    assert "PDF and chart not created" in out["warnings"][0]


def test_appendix_flows_onto_more_pages_and_keeps_long_conclusion(capsys):
    _, out = run(capsys, "analyze", "--topic", "Astronomy", "--langs", "uk,pl,tr,vi,id,pt,cs,de", "--months", "120")
    long = "Висновок агента, дуже довгий. " * 40  # > 700 chars: cut on page 1, kept in full in the appendix
    _, rep = run(capsys, "report", "--run-id", out["run_id"], "--conclusion", long)
    pdf = PdfReader(rep["files"]["pdf"])
    pages = [pg.extract_text() for pg in pdf.pages]
    assert len(pages) >= 4  # 120 monthly rows cannot fit on one appendix page
    assert "Повний висновок" in pages[1]
    appendix = "".join(pages[1:])
    assert "2016-09" in appendix and "2026-08" in appendix  # first and last month, nothing dropped
