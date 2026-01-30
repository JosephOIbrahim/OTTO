# Citations & References

This document provides formal citations for the theoretical foundations and prior work that Otto builds upon.

---

## Primary Citations

### ThinkingMachines Batch-Invariance

```bibtex
@article{he2025defeating,
  title     = {Defeating Nondeterminism in LLM Inference},
  author    = {He, Horace and {Thinking Machines Lab}},
  journal   = {Thinking Machines Lab: Connectionism},
  year      = {2025},
  month     = {September},
  url       = {https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/},
  note      = {Foundational work on achieving deterministic LLM inference through fixed evaluation order and batch-invariance}
}
```

**Key Principles Applied:**
- Fixed evaluation order regardless of batch size
- Parameter locking before generation
- Deterministic checksums for reproducibility
- No dynamic algorithm switching based on runtime conditions

---

### Universal Scene Description (USD)

```bibtex
@misc{pixar2016usd,
  title        = {Universal Scene Description},
  author       = {{Pixar Animation Studios}},
  year         = {2016},
  howpublished = {\url{https://graphics.pixar.com/usd/}},
  note         = {Open-source framework for interchange of 3D graphics data}
}

@inproceedings{elkoura2019usd,
  title     = {A Deep Dive into Universal Scene Description},
  author    = {Elkoura, George and Hiebert, Sebastian and Paskin, Michael},
  booktitle = {SIGGRAPH 2019 Courses},
  year      = {2019},
  publisher = {ACM},
  doi       = {10.1145/3305366.3328028}
}
```

**Concepts Adapted:**
- **LIVRPS Composition** → Cognitive priority resolution
- **Prim Attributes** → Behavioral parameters
- **Layers** → Cognitive subsystems (L0-L13)
- **Variants** → Mode switching (focused/exploring/recovery)
- **Payloads** → Domain knowledge (loaded on demand)

---

### Mixture of Experts (MoE)

```bibtex
@article{shazeer2017outrageously,
  title   = {Outrageously Large Neural Networks: The Sparsely-Gated Mixture-of-Experts Layer},
  author  = {Shazeer, Noam and Mirhoseini, Azalia and Maziarz, Krzysztof and Davis, Andy and Le, Quoc and Hinton, Geoffrey and Dean, Jeff},
  journal = {arXiv preprint arXiv:1701.06538},
  year    = {2017}
}

@article{fedus2022switch,
  title   = {Switch Transformers: Scaling to Trillion Parameter Models with Simple and Efficient Sparsity},
  author  = {Fedus, William and Zoph, Barret and Shazeer, Noam},
  journal = {Journal of Machine Learning Research},
  volume  = {23},
  number  = {120},
  pages   = {1--39},
  year    = {2022}
}
```

**Adaptation (ADHD_MoE):**
- 7 intervention experts with fixed priority routing
- First-match-wins semantics (no load balancing)
- Safety-first expert ordering (Validator > Scaffolder > ... > Direct)

---

### ADHD & Executive Function Research

```bibtex
@article{barkley1997adhd,
  title     = {ADHD and the Nature of Self-Control},
  author    = {Barkley, Russell A.},
  publisher = {Guilford Press},
  year      = {1997},
  note      = {Foundational work on executive function deficits in ADHD}
}

@article{brown2005executive,
  title   = {Attention Deficit Disorder: The Unfocused Mind in Children and Adults},
  author  = {Brown, Thomas E.},
  publisher = {Yale University Press},
  year    = {2005},
  note    = {Executive function model for ADHD}
}
```

**Framework Applications:**
- Working memory limits (max 3 items without structure)
- Time blindness compensation (exchange count proxy)
- Momentum protection (don't break flow)
- Recovery without guilt (rest is productive)

---

### Cognitive Load Theory

```bibtex
@article{sweller1988cognitive,
  title   = {Cognitive Load During Problem Solving: Effects on Learning},
  author  = {Sweller, John},
  journal = {Cognitive Science},
  volume  = {12},
  number  = {2},
  pages   = {257--285},
  year    = {1988}
}

@article{paas2003cognitive,
  title   = {Cognitive Load Theory and Instructional Design: Recent Developments},
  author  = {Paas, Fred and Renkl, Alexander and Sweller, John},
  journal = {Educational Psychologist},
  volume  = {38},
  number  = {1},
  pages   = {1--4},
  year    = {2003}
}
```

**Applications:**
- MAX3 bounded reflection (limit cognitive overhead)
- Chunked task presentation (max 5 visible)
- Progressive disclosure in error handling

---

### Attractor Dynamics & Dynamical Systems

```bibtex
@book{strogatz2015nonlinear,
  title     = {Nonlinear Dynamics and Chaos},
  author    = {Strogatz, Steven H.},
  publisher = {Westview Press},
  edition   = {2nd},
  year      = {2015}
}

@article{kelso1995dynamic,
  title   = {Dynamic Patterns: The Self-Organization of Brain and Behavior},
  author  = {Kelso, J. A. Scott},
  publisher = {MIT Press},
  year    = {1995}
}
```

**RC^+xi Convergence Tracking:**
- Epistemic tension as distance metric: `xi_n = ||A_{n+1} - A_n||_2`
- Attractor basins: focused, exploring, recovery, teaching
- Convergence threshold: ε = 0.1
- Stable exchanges required: 3

---

## Software Dependencies

### Core Dependencies

| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| [pydantic](https://pydantic-docs.helpmanual.io/) | ≥2.0.0 | MIT | Data validation and settings |
| [aiohttp](https://docs.aiohttp.org/) | ≥3.8.0 | Apache-2.0 | Async HTTP client/server |
| [rich](https://rich.readthedocs.io/) | ≥13.0.0 | MIT | Terminal formatting |

### Optional Dependencies

| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| [textual](https://textual.textualize.io/) | ≥0.40.0 | MIT | TUI dashboard |
| [pytest](https://pytest.org/) | ≥7.0.0 | MIT | Testing framework |
| [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) | ≥0.21.0 | Apache-2.0 | Async test support |

---

## Related Work

### Cognitive Architectures

```bibtex
@article{laird2017soar,
  title   = {A Standard Model of the Mind: Toward a Common Computational Framework across Artificial Intelligence, Cognitive Science, Neuroscience, and Robotics},
  author  = {Laird, John E. and Lebiere, Christian and Rosenbloom, Paul S.},
  journal = {AI Magazine},
  volume  = {38},
  number  = {4},
  pages   = {13--26},
  year    = {2017}
}

@book{anderson2007act,
  title     = {How Can the Human Mind Occur in the Physical Universe?},
  author    = {Anderson, John R.},
  publisher = {Oxford University Press},
  year      = {2007},
  note      = {ACT-R cognitive architecture}
}
```

### LLM Agent Frameworks

```bibtex
@article{yao2023react,
  title   = {ReAct: Synergizing Reasoning and Acting in Language Models},
  author  = {Yao, Shunyu and Zhao, Jeffrey and Yu, Dian and Du, Nan and Shafran, Izhak and Narasimhan, Karthik and Cao, Yuan},
  journal = {arXiv preprint arXiv:2210.03629},
  year    = {2023}
}

@article{wang2023selfconsistency,
  title   = {Self-Consistency Improves Chain of Thought Reasoning in Language Models},
  author  = {Wang, Xuezhi and Wei, Jason and Schuurmans, Dale and Le, Quoc and Chi, Ed and Narang, Sharan and Chowdhery, Aakanksha and Zhou, Denny},
  journal = {arXiv preprint arXiv:2203.11171},
  year    = {2023}
}
```

---

## License

Otto is released under the MIT License. See [LICENSE](LICENSE) for details.

The theoretical frameworks and research cited above are the intellectual property of their respective authors and institutions. This project builds upon their work with attribution but does not claim ownership of the underlying concepts.

---

*Otto v5.0.1 — Cognitive Engine for Claude Code*
