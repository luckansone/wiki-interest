"""Report: chart PNG and the PDF (one-page summary + flowing appendix), matplotlib only.

Import the functions from here; `style` must be imported before pyplot (it selects the Agg backend).
"""

from wiki_interest.report.charts import save_chart_png
from wiki_interest.report.pdf import save_pdf


__all__ = ["save_chart_png", "save_pdf"]
