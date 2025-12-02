"""Note generation module for Transcrib8.
Generates structured study notes from lecture transcripts using OpenAI GPT.

This version supports markdown and JSON output, chunking long transcripts,
and a deterministic fallback when the API fails.
"""

import os
import json
from pathlib import Path
from typing import Optional, List
from openai import OpenAI
from dotenv import load_dotenv


def get_api_key() -> str:
    """Get OpenAI API key preferring environment/.env, with optional legacy config.py fallback."""
    # Load environment variables from .env if present
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    # Legacy fallback: parse config.py if present (kept for compatibility)
    config_path = Path(__file__).parent.parent / "config.py"
    if config_path.exists():
        for encoding in ["utf-8", "utf-8-sig", "utf-16", "utf-16-le", "latin-1", "cp1252"]:
            try:
                with open(config_path, "r", encoding=encoding) as f:
                    content = f.read()
                # Strip BOM and search
                content = content.lstrip("\ufeff")
                if "OPENAI_API_KEY" in content:
                    for raw in content.splitlines():
                        line = raw.lstrip("\ufeff").strip()
                        if line.startswith("OPENAI_API_KEY"):
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if key:
                                return key
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as e:  # pragma: no cover
                print(f"Warning: Could not parse config.py: {e}")
    raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY in environment or .env file.")


# Configuration constants (can be overridden with env vars)
MODEL_NAME = os.getenv("NOTES_MODEL", "gpt-3.5-turbo")
MAX_COMPLETION_TOKENS = int(os.getenv("NOTES_MAX_TOKENS", "2200"))
CHUNK_CHAR_LIMIT = int(os.getenv("NOTES_CHUNK_CHAR_LIMIT", "4000"))
MAX_CHUNKS = int(os.getenv("NOTES_MAX_CHUNKS", "6"))


def build_prompt(transcript: str, title: str) -> str:
    """Build a markdown-focused prompt for structured study notes with mindmap bubbles."""
    return (
        "You are an expert study assistant.\n"
        "Create clear, exam-focused notes from the transcript. Also identify the top study concepts as 'mindmap bubbles'.\n\n"
        f"Title: {title}\n\n"
        "OUTPUT FORMAT (Markdown only):\n"
        "## Summary\n"
        "- 2-4 sentence overview that captures scope and stakes.\n\n"
        "## Key Concepts\n"
        "- 8-15 bullet points. Each: term - short explanation (<=140 chars).\n\n"
        "## Mindmap Bubbles\n"
        "- List the 6-10 most important concepts, one per line, using this format: **Concept** — why it matters (<=100 chars).\n\n"
        "## Important Details\n"
        "- 10-25 bullets of facts, numbers, or formulas (each <120 chars).\n\n"
        "## Study Questions\n"
        "- 5 questions (2 easy, 2 medium, 1 hard) - no answers.\n\n"
        "Constraints:\n"
        "- Be detailed and dense with useful information.\n- Do not invent unsupported content.\n- Prefer specific terminology and examples from transcript.\n"
        "- Avoid generic filler.\n\n"
        "TRANSCRIPT START\n"
        f"{transcript}\n"
        "TRANSCRIPT END"
    )


def build_json_prompt(transcript: str, title: str) -> str:
    """Build a JSON-focused prompt for structured study notes including mindmap bubbles."""
    return (
        "You are an expert study assistant.\n"
    "Extract structured study notes from the entire transcript below.\n"
        "Return ONLY valid JSON.\n\n"
        "Fields:\n"
        "  title: string\n"
        "  summary: string (2-3 sentences)\n"
        "  key_concepts: array of objects {term, explanation}\n"
        "  important_details: array of strings (facts, formulas, numbers)\n"
        "  study_questions: array of objects {question, difficulty in ['easy','medium','hard']}\n"
        "  mindmap_bubbles: array of objects {concept, reason, importance} (importance integer 1-5; top 6-10 most important concepts)\n"
        "  transcript_character_count: integer\n\n"
        "Rules:\n"
    " - Cover the whole lecture; avoid repetition and merge overlapping points.\n"
    " - Do not hallucinate content.\n"
        " - Provide exactly 5 study_questions (2 easy, 2 medium, 1 hard).\n"
        " - Provide 10-20 important_details entries if the transcript length permits.\n"
        " - Provide 8-15 key_concepts entries if the transcript length permits.\n"
        " - Keep explanations concise and factual.\n\n"
        "TRANSCRIPT START\n"
        f"{transcript}\n"
        "TRANSCRIPT END"
    )


def _chunk_transcript(transcript: str) -> List[str]:
    """Split long transcript into character-sized chunks."""
    if len(transcript) <= CHUNK_CHAR_LIMIT:
        return [transcript]
    chunks: List[str] = []
    for i in range(0, len(transcript), CHUNK_CHAR_LIMIT):
        if len(chunks) >= MAX_CHUNKS:
            break
        chunks.append(transcript[i : i + CHUNK_CHAR_LIMIT])
    return chunks

def _dedupe_lines(lines: List[str]) -> List[str]:
    """Remove near-duplicate lines by normalized content."""
    seen = set()
    out: List[str] = []
    for line in lines:
        norm = " ".join(line.lower().split())[:200]
        if norm and norm not in seen:
            seen.add(norm)
            out.append(line)
    return out


def _summarize_chunk(client: OpenAI, chunk: str, idx: int, total: int) -> str:
    """Summarize a chunk for later aggregation."""
    prompt = (
        f"You are condensing part {idx}/{total} of a lecture transcript.\n"
        "Extract 4-8 bullet points capturing unique key concepts, formulas, or facts.\n"
        "Avoid repetition across parts; include only novel, salient information.\nPART START\n"
        f"{chunk}\nPART END"
    )
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "Return ONLY bullet points."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=300,
    )
    content = resp.choices[0].message.content.strip()
    bullets = [l.strip("- ") for l in content.splitlines() if l.strip()]
    bullets = _dedupe_lines(bullets)
    return "\n".join(f"- {b}" for b in bullets)


def generate_structured_notes(
    transcript: str,
    title: str = "Lecture Notes",
    format_type: str = "markdown",
    api_key: Optional[str] = None,
) -> str:
    """Generate structured notes (markdown or json)."""
    if not transcript or len(transcript.strip()) < 80:
        if format_type.lower() == "json":
            return json.dumps(
                {
                    "title": title,
                    "summary": "Transcript too short to generate meaningful notes.",
                    "key_concepts": [],
                    "important_details": [],
                    "study_questions": [],
                    "transcript_character_count": len(transcript),
                },
                indent=2,
            )
        return "Transcript too short to generate meaningful notes."

    try:
        if not api_key:
            api_key = get_api_key()
        client = OpenAI(api_key=api_key)

        # Chunk + summarize if large
        chunks = _chunk_transcript(transcript)
        condensed = transcript
        if len(chunks) > 1:
            summaries = [
                _summarize_chunk(client, chunk, i + 1, len(chunks))
                for i, chunk in enumerate(chunks)
            ]
            flat = []
            for s in summaries:
                flat.extend([l.strip("- ") for l in s.splitlines() if l.strip()])
            flat = _dedupe_lines(flat)
            flat_text = "\n".join(f"- {b}" for b in flat)
            condensed = (
                f"SYNTHESIZED BULLET SUMMARIES (original length {len(transcript)} chars)\n"
                + flat_text
            )

        if format_type.lower() == "json":
            prompt = build_json_prompt(condensed, title)
        else:
            prompt = build_prompt(condensed, title)

        print(f"📝 Generating {format_type} notes with {MODEL_NAME}...")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "Produce only the requested format; concise, factual, structured.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=MAX_COMPLETION_TOKENS,
        )
        output = response.choices[0].message.content.strip()

        if format_type.lower() == "json":
            try:
                data = json.loads(output)
                data.setdefault("title", title)
                data.setdefault("transcript_character_count", len(transcript))
                # Ensure mindmap_bubbles exists
                data.setdefault("mindmap_bubbles", [])
                # Normalize importance scores (1-5)
                if isinstance(data.get("mindmap_bubbles"), list):
                    for b in data["mindmap_bubbles"]:
                        if isinstance(b, dict):
                            imp = b.get("importance", 3)
                            try:
                                imp_int = int(imp)
                            except Exception:
                                imp_int = 3
                            b["importance"] = max(1, min(5, imp_int))
                return json.dumps(data, indent=2)
            except json.JSONDecodeError:
                # Try to extract a mindmap section from text if the model returned markdown-like output
                bubbles = _extract_bubbles_from_text(output)
                return json.dumps(
                    {
                        "title": title,
                        "raw_output": output,
                        "error": "JSON parsing failed",
                        "transcript_character_count": len(transcript),
                        "mindmap_bubbles": bubbles,
                    },
                    indent=2,
                )
        return output
    except Exception as e:  # pragma: no cover
        print(f"⚠️ GPT failed: {e}. Using fallback...")
        return generate_simple_notes(transcript, title, format_type)


def generate_simple_notes(
    transcript: str, title: str = "Notes", format_type: str = "markdown"
) -> str:
    """Simple deterministic fallback (markdown or json)."""
    sentences = transcript.replace(".", ".\n").split("\n")
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 40]
    key_points = sentences[::3][:10]
    if format_type.lower() == "json":
        return json.dumps(
            {
                "title": title,
                "summary": "Fallback notes (AI unavailable).",
                "key_concepts": [
                    {"term": f"Point {i+1}", "explanation": kp[:120]}
                    for i, kp in enumerate(key_points)
                ],
                "important_details": key_points[:10],
                "study_questions": [],
                "mindmap_bubbles": [
                    {"concept": f"Concept {i+1}", "reason": kp[:90], "importance": 3}
                    for i, kp in enumerate(key_points[:8])
                ],
                "transcript_character_count": len(transcript),
            },
            indent=2,
        )
    lines = [
        f"# {title}",
        "## Summary",
        "Fallback notes (AI unavailable).",
        "## Key Concepts",
    ]
    for kp in key_points:
        lines.append(f"- {kp}")
    lines.extend(["", "## Full Transcript", transcript])
    return "\n".join(lines)


def _extract_bubbles_from_text(text: str) -> List[dict]:
    """Heuristic: parse lines under 'Mindmap Bubbles' to build bubble objects.
    Expected format per line: '- **Concept** — reason'. Importance defaults to 3.
    """
    lines = text.splitlines()
    bubbles: List[dict] = []
    in_section = False
    for line in lines:
        l = line.strip()
        if not in_section:
            if l.lower().startswith("## mindmap bubbles"):
                in_section = True
            continue
        # stop when another heading starts
        if l.startswith("## ") or l.startswith("# "):
            break
        if l.startswith("-"):
            # remove leading '-'
            s = l[1:].strip()
            # match **Concept** — reason
            concept = None
            reason = ""
            if s.startswith("**"):
                # find closing **
                try:
                    end = s.index("**", 2)
                    concept = s[2:end].strip()
                    after = s[end+2:].strip()
                    # split on em dash or dash
                    if after.startswith("—") or after.startswith("-"):
                        reason = after[1:].strip()
                    else:
                        reason = after
                except ValueError:
                    concept = s.strip()
            else:
                # fallback: until dash
                parts = s.split("—", 1)
                if len(parts) == 2:
                    concept = parts[0].strip()
                    reason = parts[1].strip()
                else:
                    concept = s.strip()
            if concept:
                bubbles.append({"concept": concept, "reason": reason, "importance": 3})
            if len(bubbles) >= 12:
                break
    return bubbles


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python notes.py <transcript_file> [title] [format: markdown|json]")
        sys.exit(1)
    transcript_path = Path(sys.argv[1])
    if not transcript_path.exists():
        print(f"File not found: {transcript_path}")
        sys.exit(1)
    title_arg = sys.argv[2] if len(sys.argv) > 2 else "Lecture Notes"
    fmt = sys.argv[3] if len(sys.argv) > 3 else "markdown"
    with open(transcript_path, "r", encoding="utf-8") as f:
        txt = f.read()
    result = generate_structured_notes(txt, title_arg, fmt)
    out_ext = "json" if fmt.lower() == "json" else "md"
    out_file = transcript_path.with_name(transcript_path.stem + f"_notes.{out_ext}")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"Saved notes to {out_file}")
    
    transcript_file = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else "Lecture Notes"
    
    try:
        # Read transcript
        with open(transcript_file, 'r', encoding='utf-8') as f:
            transcript = f.read()
        
        print(f"📚 Generating notes from: {transcript_file}")
        print(f"📝 Title: {title}\n")
        
        # Generate notes
        notes = generate_structured_notes(transcript, title)
        
        # Save to file
        output_file = f"{Path(transcript_file).stem}_notes.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(notes)
        
        print(f"\n✅ Saved to: {output_file}")
        print("\nPreview:")
        print("=" * 80)
        print(notes[:500] + "..." if len(notes) > 500 else notes)
        print("=" * 80)
    
    except FileNotFoundError:
        print(f"❌ Error: File not found: {transcript_file}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
