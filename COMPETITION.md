# PLLM Competition Platform

## Overview
Agentic engineering has advanced wildly over recent years. Since ChatGPT took the spotlight back in 2022, we've seen frontier models frequently push the boundaries of what we thought possible.

This inaugural competition advances agentic approaches for Python dependency resolution. Building on Bartlett et al. (2025)~\cite{bartlett2025dependencycrusadesolvingpython}, we encourage researchers to focus on open-source memory constrained techniques, such as innovation in RAG, multi-agent systems, graph-based databases, few-shot learning, and build feedback optimization.
Dependency conflicts remain a daily challenge due to an ever increasing module library, combined with Python use adoption~\cite{10684593}. This competition recognises agentic engineering as a possible solution to this problem.

## Getting Started
To begin, we suggest building the PLLM docker container and running the sameple gists to understand how existing works have tackled this problem.



## Baseline System Overview

Participants are envouraged to build upon and improve the baseline approach; PLLM~\cite{bartlett2025dependencycrusadesolvingpython} (5-stage RAG+LLM pipeline): extract dependencies → Docker build → error log analysis → generate specs → validate → iterate.

### Dataset
HG2.9K (2,900+ Python files with hard conflicts). \textbf{Constraints}: Docker environment, 10GB VRAM limit. Independent evaluation on held-out dataset for final tool results during the event.

### Evaluation Metrics
- *Success Rate*: Number of successfully resolved files
- *Efficiency*: Time taken to resolve the new dataset
- *Computational Cost*: Time/resources (10GB VRAM limit)
- *Generalization*: Performance on held-out conflicts