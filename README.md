# 🧠 Re:Learn
## Adaptive Multimodal Learning Environment

> **Re:Learn doesn't just identify that a learner is wrong — it identifies WHY they are wrong and adapts until the misconception is resolved.**

---

## 📌 Overview

Traditional Learning Management Systems (LMS) generally follow a fixed sequence of lectures, PDFs, videos, assignments, and quizzes.

Even adaptive systems often focus mainly on changing question difficulty.

The problem is that a wrong answer does not always mean that a student simply "doesn't know the topic."

A learner may:

- Know the formula but apply it incorrectly
- Understand the concept but make a specific reasoning error
- Misunderstand a programming rule
- Have an incorrect assumption about a physical principle
- Make a mistake that reveals a deeper misconception                                                                                                             
## 🚀 Live Demo

👉 [**Open Re:Learn Website**](https://relearnnn.lovable.app)

## 📂 Project Structure

- `frontend/` — Frontend application
- `app/` — Backend
- `main.py` — Backend entry point
### Re:Learn takes a different approach.

Instead of simply marking a response as incorrect, Re:Learn analyzes the learner's:

- 📝 Answer
- ✏️ Working / steps
- 💻 Code
- 💭 Reasoning

It then identifies the likely underlying misconception, provides a targeted intervention, and reassesses the learner using a new problem based on the same concept.

---

# 🎯 Problem Statement

Most learning platforms follow this pattern:

```text
Student attempts question
        ↓
Answer is wrong
        ↓
Marked "Incorrect"
        ↓
Correct answer is shown
        ↓
Student moves on
