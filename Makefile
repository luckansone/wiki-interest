uv_install_deps:
	uv sync
uv_install_deps_runtime:
	uv sync --no-dev
uv_get_lock:
	uv lock
uv_update_deps:
	uv sync --frozen
uv_update_self:
	uv self update
uv_show_deps:
	uv pip list
uv_show_deps_tree:
	uv tree

pre_commit_install: .pre-commit-config.yaml
	uv run pre-commit install
pre_commit_run: .pre-commit-config.yaml
	uv run pre-commit run --all-files
pre_commit_rm_hooks:
	uv run pre-commit uninstall

lint:
	uv run ruff check
	uv run ruff format --check
format:
	uv run ruff check --fix
	uv run ruff format
test:
	uv run pytest
test_cov:
	uv run pytest --cov --cov-report=term-missing

# Offline demo run: synthetic Wikimedia responses, report gets a red "DEMO" banner.
demo:
	WI_FAKE_API=1 bash scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs --months 24 --pdf
# Agent loop on a cheap model (needs OPENROUTER_API_KEY).
#   make eval                                   free Nemotron 3 Super, synthetic Wikimedia data
#   make eval MODEL=anthropic/claude-haiku-4.5 EVAL_ARGS="--repeats 2"   live data
MODEL ?= nvidia/nemotron-3-super-120b-a12b:free
EVAL_ARGS ?= --fake-api
eval:
	uv run python evals/run_eval.py --model $(MODEL) $(EVAL_ARGS)

# Upload package for Claude (limit 30 MB): an explicit allowlist, so .venv, caches, run outputs
# and local settings (.claude/) never get in. The zip root is the skill folder: wiki-interest/SKILL.md.
SKILL_NAME = wiki-interest
SKILL_FILES = SKILL.md README.md pyproject.toml uv.lock \
	references scripts tests evals/run_eval.py evals/scenarios.json
skill_zip:
	rm -rf dist/$(SKILL_NAME) dist/$(SKILL_NAME).zip
	mkdir -p dist/$(SKILL_NAME)
	rsync -aR --exclude "__pycache__" --exclude "*.pyc" $(SKILL_FILES) dist/$(SKILL_NAME)/
	cd dist && zip -qrX $(SKILL_NAME).zip $(SKILL_NAME)
	rm -rf dist/$(SKILL_NAME)
	@ls -lh dist/$(SKILL_NAME).zip | awk '{print "dist/$(SKILL_NAME).zip: " $$5}'

.PHONY: uv_install_deps uv_install_deps_runtime uv_get_lock uv_update_deps uv_update_self uv_show_deps \
	uv_show_deps_tree pre_commit_install pre_commit_run pre_commit_rm_hooks \
	lint format test test_cov demo eval skill_zip
