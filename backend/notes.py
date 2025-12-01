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
MAX_COMPLETION_TOKENS = int(os.getenv("NOTES_MAX_TOKENS", "1800"))
CHUNK_CHAR_LIMIT = int(os.getenv("NOTES_CHUNK_CHAR_LIMIT", "4000"))
MAX_CHUNKS = int(os.getenv("NOTES_MAX_CHUNKS", "5"))


def build_prompt(transcript: str, title: str) -> str:
    """Build a markdown-focused prompt for structured study notes."""
    return (
        "You are an expert study assistant.\n"
        "Create clear, exam-focused notes from the transcript.\n\n"
        f"Title: {title}\n\n"
        "OUTPUT FORMAT (Markdown only):\n"
        "## Summary\n"
        "- 2-3 sentence overview.\n\n"
        "## Key Concepts\n"
        "- 5-10 bullet points. Each: term - short explanation.\n\n"
        "## Important Details\n"
        "- Facts, numbers, formulas (bullet list, each line <120 chars).\n\n"
        "## Study Questions\n"
        "- 5 questions (2 easy, 2 medium, 1 hard) - no answers.\n\n"
        "Constraints:\n"
        "- Be concise.\n- Do not invent unsupported content.\n"
        "- Avoid generic filler.\n\n"
        "TRANSCRIPT START\n"
        f"{transcript}\n"
        "TRANSCRIPT END"
    )


def build_json_prompt(transcript: str, title: str) -> str:
    """Build a JSON-focused prompt for structured study notes."""
    return (
        "You are an expert study assistant.\n"
        "Extract structured study notes from the transcript below.\n"
        "Return ONLY valid JSON.\n\n"
        "Fields:\n"
        "  title: string\n"
        "  summary: string (2-3 sentences)\n"
        "  key_concepts: array of objects {term, explanation}\n"
        "  important_details: array of strings (facts, formulas, numbers)\n"
        "  study_questions: array of objects {question, difficulty in ['easy','medium','hard']}\n"
        "  transcript_character_count: integer\n\n"
        "Rules:\n"
        " - Do not hallucinate content.\n"
        " - Provide exactly 5 study_questions (2 easy, 2 medium, 1 hard).\n"
        " - Keep explanations concise.\n\n"
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


def _summarize_chunk(client: OpenAI, chunk: str, idx: int, total: int) -> str:
    """Summarize a chunk for later aggregation."""
    prompt = (
        f"You are condensing part {idx}/{total} of a lecture transcript.\n"
        "Extract 3-6 bullet points capturing key concepts or facts.\n"
        "Avoid repetition.\nPART START\n"
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
    return resp.choices[0].message.content.strip()


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
            condensed = (
                f"SYNTHESIZED BULLET SUMMARIES (original length {len(transcript)} chars)\n"
                + "\n".join(summaries)
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
            temperature=0.6,
            max_tokens=MAX_COMPLETION_TOKENS,
        )
        output = response.choices[0].message.content.strip()

        if format_type.lower() == "json":
            try:
                data = json.loads(output)
                data.setdefault("title", title)
                data.setdefault("transcript_character_count", len(transcript))
                return json.dumps(data, indent=2)
            except json.JSONDecodeError:
                return json.dumps(
                    {
                        "title": title,
                        "raw_output": output,
                        "error": "JSON parsing failed",
                        "transcript_character_count": len(transcript),
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
                "important_details": key_points[:5],
                "study_questions": [],
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
