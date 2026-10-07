#!/usr/bin/env bash
# Copy the repo's dbt project into the Astro project's include/ folder.
#
# Astro only puts files under airflow/ into the image, and the dbt project lives one
# level up in ../dbt. Run this before `astro dev start` and again after any dbt change.
# The copy is git-ignored, so ../dbt stays the single source of truth.
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
src="$here/../dbt"
dst="$here/include/dbt"

rm -rf "$dst"
mkdir -p "$dst"
# Copy the project, not local build output.
( cd "$src" && tar --exclude=target --exclude=logs --exclude=dbt_packages -cf - . ) | ( cd "$dst" && tar -xf - )
echo "synced $src -> $dst"
