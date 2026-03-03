#!/bin/bash

python Galaxy.py \
--model "google/gemini-2.5-pro" \
--reasoning-effort "low"

python MiroFlow.py \
--model "google/gemini-2.5-pro" \
--reasoning-effort "low"

python shiyu.py \
--model "google/gemini-2.5-pro" \
--reasoning-effort "low"