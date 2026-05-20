# User Research Interest Profile

## Overview
CMU MS student (Mobile/IoT Engineering) pursuing PhD-track research at the intersection of robotics, world models, and AI infrastructure. Values **novelty** above all — incremental improvements on existing methods are not interesting unless they introduce a genuinely new angle.

## Primary Research Interests (High Priority)

### 1. Robotics Learning
- **Reinforcement learning for locomotion & manipulation**: PPO, SAC, skill decomposition, curriculum learning, gravity curriculum, sim-to-real transfer
- **Humanoid robot control**: acrobatic skills (backflip), whole-body control, motion tracking, contact-rich interactions
- **Skill transfer & hierarchical RL**: initializing complex skills from simpler pretrained policies, primitive discovery (OPAL-style), temporal abstraction
- **VLMs as critics/teachers for robot RL**: using vision-language models to diagnose movement failures, generate reward functions, provide structured feedback for physics-intensive tasks
- **Reward design & reward hacking**: robust reward models, semantic reward functions, pitfalls of penalty-based rewards vs. positive-behavior rewards
- **Diffusion-based policies**: SkillDiffuser, 3D Diffuser Actor, action diffusion, flow matching for robot control

### 2. World Models
- **Video world models for robotics**: learning physics from video, predicting future states, action-conditioned generation
- **Next-generation AI architectures**: alternatives or successors to Transformers, models that truly understand physics
- **Sim-to-real & data engines**: paired (observation, action, next-observation) data at scale, unified training streams from teleop + internet video + simulation
- **Latent world models**: abstraction levels, latent dynamics, model-based RL

### 3. AI Models & Algorithms (CV + NLP + Video)
- **Vision-language models**: VLM representations for RL, grounded reasoning, spatial understanding (ViGoRL-style)
- **3D scene understanding**: part-level scene graphs, 3D representations from video, object permanence
- **Video understanding & generation**: temporal consistency, video diffusion, video prediction
- **Reasoning model post-training**: o1/o3-style reasoning via RL, chain-of-thought reinforcement learning, test-time compute scaling, process reward models, reward models for reasoning verification, MCTS/tree-search for inference, distilling reasoning into smaller models, RL-based post-training pipelines (GRPO, STaR, rest-EM, etc.), reasoning in multimodal and embodied settings
- **Omni models**: unified architectures that handle text + image + audio + video + action in a single model (e.g., Gemini-style, any-to-any generation), multimodal tokenization strategies, interleaved generation, cross-modal reasoning, models that bridge perception and generation in a single forward pass
- **Preference optimization**: DPO, RLHF, reward model training, alignment, reward hacking mitigation
- **Model distillation & efficient models**: knowledge distillation, LoRA, small models for edge deployment
- **Novel architectures**: anything that challenges or extends the Transformer paradigm (state-space models, hybrid architectures, linear attention, etc.)

### 4. AI Infrastructure (Broad — Deserves Its Own Report Section)
This is a first-class interest area, not a sub-bullet. Include papers even if they are "systems" papers with no novel ML algorithm — the infrastructure itself is the contribution.

#### Training Systems
- **Distributed training at scale**: parallelism strategies (tensor/pipeline/expert/data/context), communication optimization, fault tolerance, elastic training
- **Training infrastructure for video/multimodal models**: the Megatron-LM equivalent for video world models — data pipelines, throughput optimization for video-scale action-conditioned training
- **Data engines & data curation**: automated data pipelines, data mixing strategies, deduplication, quality filtering at scale, web-scale data processing

#### Post-Training & RL Infrastructure
- **RL-based post-training systems**: infrastructure for RLHF/RLAIF at scale, reward model serving, online RL training loops for LLMs (PPO/GRPO/REINFORCE variants at scale), async actor-critic architectures for LLM training
- **Post-training pipelines**: systems for SFT → reward modeling → RL pipelines, orchestration of multi-stage post-training, evaluation infrastructure
- **Reasoning training infrastructure**: systems for generating and verifying chain-of-thought rollouts, process reward model training at scale, MCTS infrastructure for LLM reasoning

#### Inference & Serving Systems
- **Efficient LLM inference**: KV-cache optimization, speculative decoding, continuous batching, PagedAttention, disaggregated serving, prefill/decode separation
- **Efficient inference for on-robot deployment**: quantization, latent caching, hardware-aware distillation, real-time inference under latency constraints (50-200Hz)
- **Edge computing for AI**: deploying models on front-end tier devices, offloading strategies, on-device inference optimization
- **MoE serving**: expert routing efficiency, expert offloading, capacity planning for sparse models

#### Simulation & Robotics Infrastructure
- **Sim-to-real infrastructure**: simulation platforms, domain randomization pipelines, synthetic data generation at scale
- **Fleet-scale robot learning systems**: distributed data collection, policy synchronization, reward computation infrastructure for deployed robots
- **Benchmark & evaluation infrastructure**: scalable robot evaluation, sim-to-real translation for benchmarking

## Secondary Interests (Include if Particularly Novel)
- Brain-computer interfaces (BCI) — especially as the "ultimate interaction form"
- Autonomous vehicle simulation (TeraSim-style)
- Multi-agent RL (e.g., AssistMimic-style cooperative control)
- Continual / lifelong learning for embodied agents

## What Makes a Paper "Interesting"
- **Novel problem formulation** or a genuinely new angle on an existing problem
- **New architectures or paradigms** — not just "we added module X to existing pipeline Y"
- **Strong empirical results that challenge conventional wisdom**
- **Cross-domain transfer of ideas** (e.g., NLP technique applied to robotics in a non-obvious way)
- **Papers from top labs** (DeepMind, Physical Intelligence, Skild, Berkeley, CMU, Stanford, MIT) working on frontier problems

## What is NOT Interesting
- Incremental benchmark improvements without conceptual novelty
- Pure prompt-engineering papers
- Survey papers (unless the field is very new)
- Papers that only work on toy domains without clear path to real-world applicability
