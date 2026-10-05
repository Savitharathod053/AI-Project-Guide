"""
PROJECT INNOVATION & UNIQUENESS ANALYZER SERVICE
=================================================
Analyzes student project ideas for novelty, market differentiation,
real-world prior art (GitHub & arXiv), and similarity against existing
internal Campus Flow projects.

Uses real search APIs (GitHub REST API, arXiv Atom API), internal database
matching with student privacy protection, and Google Gemini with schema
validation and graceful rule-based fallback.
"""

import hashlib
import json
import logging
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from app.models import db, Project, ProjectAnalysis
from app.services.ai_service import get_ai_service

logger = logging.getLogger("projexa.uniqueness_analyzer")


class UniquenessAnalyzerService:
    """Service orchestrating novelty detection, prior art discovery, and AI analysis."""

    def __init__(self):
        self.ai_service = get_ai_service()
        self.request_timeout = 8  # Seconds for external search requests

    # =========================================================================
    # 1. INPUT HASHING & NORMALIZATION
    # =========================================================================
    @staticmethod
    def compute_input_hash(data: Dict[str, Any]) -> str:
        """Computes a SHA-256 hash of normalized user inputs for caching."""
        keys = [
            "project_title",
            "problem_statement",
            "project_description",
            "proposed_solution",
            "main_features",
            "technologies_used",
            "target_users",
        ]
        tokens = []
        for k in keys:
            val = str(data.get(k, "") or "").strip().lower()
            tokens.append(f"{k}:{val}")
        raw = "|".join(tokens)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # =========================================================================
    # 2. CONCEPT EXTRACTION & SEARCH QUERY GENERATOR
    # =========================================================================
    def generate_search_queries(
        self,
        title: str,
        problem: str,
        description: str,
        solution: str,
        features: str,
        technologies: str,
        target_users: str = ""
    ) -> List[str]:
        """
        Extracts key technical concepts and generates 3-5 meaningful search queries
        (never relying only on the exact title).
        """
        queries: List[str] = []

        # Clean title keywords
        clean_title = re.sub(r"[^\w\s]", " ", title or "").strip()
        stop_words = {
            "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of",
            "with", "by", "is", "using", "based", "system", "project", "application",
            "app", "platform", "automated", "smart", "management"
        }
        title_words = [w for w in clean_title.split() if len(w) > 2 and w.lower() not in stop_words]

        # Extract tech keywords
        tech_tokens = [t.strip() for t in re.split(r"[,;|\n]+", technologies or "") if t.strip()]
        primary_tech = tech_tokens[:3]

        # 1. Cleaned Title + Primary Domain concept
        if title_words:
            core_title_concept = " ".join(title_words[:4])
            queries.append(core_title_concept)

        # 2. Domain / Problem + Solution
        problem_snippet = (problem or description or "")[:150]
        prob_words = [
            w for w in re.sub(r"[^\w\s]", " ", problem_snippet).split()
            if len(w) > 3 and w.lower() not in stop_words
        ]
        if prob_words:
            queries.append(" ".join(prob_words[:3]))

        # 3. Technologies + Core problem keywords
        if primary_tech and prob_words:
            queries.append(f"{primary_tech[0]} {' '.join(prob_words[:2])}")
        elif primary_tech and title_words:
            queries.append(f"{primary_tech[0]} {' '.join(title_words[:2])}")

        # 4. Features extraction
        feat_words = [
            w for w in re.sub(r"[^\w\s]", " ", features or "").split()
            if len(w) > 3 and w.lower() not in stop_words
        ]
        if feat_words:
            queries.append(" ".join(feat_words[:3]))

        # Deduplicate & sanitize queries
        unique_queries = []
        for q in queries:
            q_clean = " ".join(q.split()).strip()
            if q_clean and len(q_clean) >= 4 and q_clean.lower() not in [uq.lower() for uq in unique_queries]:
                unique_queries.append(q_clean)

        if not unique_queries and clean_title:
            unique_queries = [clean_title]

        return unique_queries[:4]

    # =========================================================================
    # 3. EXTERNAL SOURCES SEARCH (GitHub REST API + arXiv Atom API)
    # =========================================================================
    def search_github_repositories(self, queries: List[str], max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Queries public GitHub Search API for authentic open-source projects.
        Strictly returns real GitHub repository URLs and descriptions.
        """
        results: List[Dict[str, Any]] = []
        seen_urls = set()

        for q in queries:
            if len(results) >= max_results:
                break
            try:
                encoded_q = urllib.parse.quote_plus(q)
                url = f"https://api.github.com/search/repositories?q={encoded_q}&sort=stars&order=desc&per_page=3"
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "CampusFlow-Innovation-Analyzer/1.0",
                        "Accept": "application/vnd.github.v3+json",
                    }
                )
                with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        items = data.get("items", [])
                        for item in items:
                            html_url = item.get("html_url")
                            if html_url and html_url.startswith("https://github.com/") and html_url not in seen_urls:
                                seen_urls.add(html_url)
                                results.append({
                                    "source_type": "GitHub Repository",
                                    "title": item.get("full_name") or item.get("name"),
                                    "description": item.get("description") or "Open source software project on GitHub.",
                                    "url": html_url,
                                    "stars": item.get("stargazers_count", 0),
                                    "language": item.get("language") or "General",
                                    "query_used": q,
                                })
                                if len(results) >= max_results:
                                    break
            except Exception as e:
                logger.info(f"GitHub search skipped or timed out for query '{q}': {e}")
                continue

        return results

    def search_arxiv_papers(self, queries: List[str], max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Queries official arXiv API for research papers matching project concepts.
        Strictly returns real arXiv URLs and paper abstracts.
        """
        results: List[Dict[str, Any]] = []
        seen_urls = set()

        for q in queries:
            if len(results) >= max_results:
                break
            try:
                encoded_q = urllib.parse.quote_plus(f"all:{q}")
                url = f"http://export.arxiv.org/api/query?search_query={encoded_q}&start=0&max_results=3"
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "CampusFlow-Innovation-Analyzer/1.0"
                    }
                )
                with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                    if resp.status == 200:
                        xml_data = resp.read().decode("utf-8")
                        root = ET.fromstring(xml_data)
                        # Atom namespace is http://www.w3.org/2005/Atom
                        ns = {"atom": "http://www.w3.org/2005/Atom"}
                        for entry in root.findall("atom:entry", ns):
                            title_elem = entry.find("atom:title", ns)
                            summary_elem = entry.find("atom:summary", ns)
                            id_elem = entry.find("atom:id", ns)

                            if title_elem is not None and id_elem is not None:
                                paper_title = " ".join((title_elem.text or "").split())
                                paper_url = (id_elem.text or "").strip()
                                paper_summary = " ".join((summary_elem.text or "").split())[:280] + "..." if summary_elem is not None and summary_elem.text else "Published research paper on arXiv."

                                # Ensure valid URL
                                if (paper_url.startswith("http://arxiv.org/abs/") or paper_url.startswith("https://arxiv.org/abs/")) and paper_url not in seen_urls:
                                    seen_urls.add(paper_url)
                                    results.append({
                                        "source_type": "Research Paper (arXiv)",
                                        "title": paper_title,
                                        "description": paper_summary,
                                        "url": paper_url,
                                        "query_used": q,
                                    })
                                    if len(results) >= max_results:
                                        break
            except Exception as e:
                logger.info(f"arXiv search skipped or timed out for query '{q}': {e}")
                continue

        return results

    def fetch_external_comparisons(self, queries: List[str]) -> List[Dict[str, Any]]:
        """Aggregates authentic GitHub repositories and arXiv scientific publications."""
        github_res = self.search_github_repositories(queries, max_results=3)
        arxiv_res = self.search_arxiv_papers(queries, max_results=2)
        return github_res + arxiv_res

    # =========================================================================
    # 4. INTERNAL CAMPUS FLOW COMPARISON (With Strict Privacy Protection)
    # =========================================================================
    def find_similar_internal_projects(
        self,
        title: str,
        problem: str,
        description: str,
        technologies: str,
        current_project_id: Optional[int] = None,
        max_results: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Identifies conceptually similar projects inside the college database.
        PRIVACY NOTICE: Strips owner identity, emails, user IDs, and private details.
        Returns only technical comparisons and similarity reasons.
        """
        try:
            query = Project.query
            if current_project_id:
                query = query.filter(Project.id != current_project_id)
            existing_projects = query.limit(50).all()
        except Exception as e:
            logger.warning(f"Error querying internal projects for comparison: {e}")
            return []

        if not existing_projects:
            return []

        input_text = f"{title} {problem} {description} {technologies}".lower()
        input_words = set(re.findall(r"\b[a-z]{3,}\b", input_text))
        input_techs = {t.strip().lower() for t in re.split(r"[,;|\n]+", technologies or "") if t.strip()}

        matches: List[Dict[str, Any]] = []

        for p in existing_projects:
            target_text = f"{p.project_name} {p.description or ''} {p.objective or ''} {p.domain or ''}".lower()
            target_words = set(re.findall(r"\b[a-z]{3,}\b", target_text))
            target_techs = {t.strip().lower() for t in re.split(r"[,;|\n]+", p.technologies or "") if t.strip()}

            # Word overlap
            shared_words = input_words.intersection(target_words)
            # Tech overlap
            shared_techs = input_techs.intersection(target_techs)

            if len(shared_words) >= 3 or shared_techs:
                overlap_score = len(shared_words) + (len(shared_techs) * 3)

                reasons = []
                if shared_techs:
                    reasons.append(f"Shares tech stack components: {', '.join(sorted(shared_techs))}")
                if len(shared_words) >= 3:
                    reasons.append(f"Overlapping domain concepts ({len(shared_words)} common keywords)")

                matches.append({
                    "score": overlap_score,
                    # Anonymized data only - strictly no student names/emails
                    "project_name": p.project_name,
                    "domain": p.domain or "General Engineering",
                    "technologies": p.technologies or "Web / Software",
                    "shared_technologies": list(shared_techs),
                    "similarity_reason": "; ".join(reasons) or "Similar technical problem space",
                })

        # Sort by overlap score descending
        matches.sort(key=lambda m: m["score"], reverse=True)
        return matches[:max_results]

    # =========================================================================
    # 5. GEMINI AI PROMPT & ANALYSIS PIPELINE
    # =========================================================================
    def analyze_project_with_ai(
        self,
        project_data: Dict[str, Any],
        external_evidence: List[Dict[str, Any]],
        internal_comparisons: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Sends structured evidence, prior art, and proposal details to Gemini.
        Returns validated, structured JSON novelty report.
        """
        title = project_data.get("project_title", "Untitled Project")
        problem = project_data.get("problem_statement", "")
        description = project_data.get("project_description", "")
        solution = project_data.get("proposed_solution", "")
        features = project_data.get("main_features", "")
        technologies = project_data.get("technologies_used", "")
        target_users = project_data.get("target_users", "")
        additional_notes = project_data.get("additional_notes", "")

        # Format evidence for prompt
        external_context = ""
        if external_evidence:
            external_context = "DISCOVERED REAL PUBLIC PRIOR ART (Do not alter URLs or fake repos):\n"
            for idx, item in enumerate(external_evidence, 1):
                external_context += (
                    f"{idx}. [{item.get('source_type')}] {item.get('title')}\n"
                    f"   URL: {item.get('url')}\n"
                    f"   Description: {item.get('description')}\n"
                )
        else:
            external_context = "No specific external public repositories or papers retrieved for these exact terms.\n"

        internal_context = ""
        if internal_comparisons:
            internal_context = "SIMILAR INTERNAL CAMPUS PROJECTS (Anonymized):\n"
            for idx, item in enumerate(internal_comparisons, 1):
                internal_context += (
                    f"{idx}. '{item.get('project_name')}' (Domain: {item.get('domain')}, Tech: {item.get('technologies')})\n"
                    f"   Similarity Note: {item.get('similarity_reason')}\n"
                )
        else:
            internal_context = "No closely matching projects found in current internal college database.\n"

        prompt = f"""You are the Project Innovation & Uniqueness Evaluator for Campus Flow (Projexa).
Analyze the student's project idea below to determine how differentiated it is compared to standard college projects and existing solutions.

IMPORTANT GUIDELINES:
1. NEVER claim the project is "100% unique" or "0% unique / completely identical". Uniqueness is an AI-assisted estimate based on available public indexed samples.
2. Provide an honest, constructive assessment. Most student projects combine common components (e.g. CRUD, standard ML models, login dashboards) with a specific application domain.
3. Be specific about what is common vs. what has potential differentiation.
4. Suggest 3 to 5 realistic, high-impact improvements to boost innovation, explaining WHY each suggestion increases uniqueness and HOW to implement it.

STUDENT PROJECT PROPOSAL:
- Title: {title}
- Problem Statement: {problem or 'Not specified'}
- Project Description: {description or 'Not specified'}
- Proposed Solution: {solution or 'Not specified'}
- Main Features: {features or 'Not specified'}
- Technologies: {technologies or 'Not specified'}
- Target Users: {target_users or 'General Users'}
- Additional Notes: {additional_notes or 'None'}

{external_context}

{internal_context}

Return ONLY valid JSON matching this exact structure:
{{
  "project_summary": "Concise 2-sentence summary of what this project does and who it is for.",
  "differentiation_score": 65,
  "innovation_level": "Moderate",
  "score_rationale": "Clear 2-sentence explanation of why this differentiation score was assigned.",
  "what_already_exists": [
    "Common element 1 (e.g., standard user authentication and database storage)",
    "Common element 2 (e.g., pre-trained OpenCV face detection algorithms)",
    "Common element 3 (e.g., standard admin reporting dashboard)"
  ],
  "potentially_unique_aspects": [
    "Differentiating feature or domain application 1",
    "Novel data source or contextual workflow 2"
  ],
  "similar_external_projects": [
    {{
      "title": "Exact title from discovered prior art",
      "source_type": "GitHub Repository or Research Paper",
      "url": "Exact URL from discovered prior art",
      "summary": "Brief summary of the external solution",
      "relation_to_student_project": "How this relates or compares to the student's idea"
    }}
  ],
  "similar_internal_projects": [
    {{
      "project_name": "Project name from internal list",
      "domain": "Domain",
      "shared_aspects": "Key overlapping features or technologies",
      "differentiation_note": "How the student's idea differs from this campus project"
    }}
  ],
  "improvement_suggestions": [
    {{
      "title": "Actionable innovation title",
      "suggested_direction": "Concrete feature or capability to add",
      "why_it_improves_uniqueness": "Detailed explanation of why this elevates the project above common solutions",
      "implementation_hint": "Practical technical approach (e.g., API, model, architecture pattern)",
      "difficulty": "Medium"
    }}
  ],
  "final_verdict": "Encouraging, realistic concluding summary with strategic guidance.",
  "disclaimer": "This analysis is an AI-assisted evaluation based on public code repositories and internal database comparisons. It does not constitute a formal patent search or guarantee global novelty."
}}
"""
        parsed = None
        if self.ai_service.gemini_key:
            try:
                res_text = self.ai_service._call_gemini_api(prompt)
                parsed = self.ai_service._extract_json(res_text)
            except Exception as e:
                logger.warning(f"Gemini API call failed during Uniqueness Analysis: {e}")

        # If LLM API failed or returned malformed JSON, use fallback generator
        if not parsed or not isinstance(parsed, dict) or "differentiation_score" not in parsed:
            logger.info("Using rule-based uniqueness report fallback.")
            parsed = self._generate_rule_based_report(
                project_data,
                external_evidence,
                internal_comparisons
            )

        # Post-process & guarantee required structure and real URLs
        parsed = self._sanitize_and_validate_report(parsed, external_evidence, internal_comparisons, title)
        return parsed

    # =========================================================================
    # 6. RULE-BASED FALLBACK REPORT GENERATOR
    # =========================================================================
    def _generate_rule_based_report(
        self,
        project_data: Dict[str, Any],
        external_evidence: List[Dict[str, Any]],
        internal_comparisons: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generates a robust, realistic novelty analysis if AI services are unavailable.
        Uses heuristic scoring based on technical specificity, domain depth, and prior art count.
        """
        title = project_data.get("project_title", "Untitled Project")
        desc = project_data.get("project_description", "")
        features = project_data.get("main_features", "")
        tech = project_data.get("technologies_used", "")
        problem = project_data.get("problem_statement", "")
        solution = project_data.get("proposed_solution", "")

        # Heuristic scoring
        base_score = 52
        if len(desc) > 150:
            base_score += 8
        if len(features) > 80:
            base_score += 6
        if len(tech) > 20:
            base_score += 4
        if len(external_evidence) >= 3:
            base_score -= 8  # Substantial prior art found
        if len(internal_comparisons) >= 2:
            base_score -= 6  # Substantial college overlap found

        # Clamp between 30 and 85 (never 0 or 100)
        score = max(30, min(85, base_score))

        if score < 45:
            level = "Low"
            rationale = "Multiple existing solutions and standard templates exist for this problem space. Adding specialized algorithms or offline support will increase differentiation."
        elif score < 70:
            level = "Moderate"
            rationale = "The core problem and tech stack are established in open-source projects, but your workflow combination and user targeting provide good practical value."
        elif score < 85:
            level = "Good"
            rationale = "Your proposal features distinct workflow integrations and technical depth beyond standard academic templates."
        else:
            level = "High"
            rationale = "Strong novel problem framing and modern technical combination with few direct academic duplicates."

        # Existing aspects
        existing = [
            f"Core data models and CRUD operations for {title}",
            "Standard user authentication, role management, and storage",
            f"Common open-source libraries in {tech or 'standard frameworks'}"
        ]

        # Potential unique aspects
        unique_aspects = [
            f"Tailored problem application focusing on: {problem[:80] if problem else 'target college user workflows'}",
            f"Combined feature pipeline: {features[:80] if features else 'integrated user dashboard'}",
        ]

        # Improvement suggestions
        improvements = [
            {
                "title": "Add Real-time Anomaly Detection / Feedback Loop",
                "suggested_direction": "Integrate an event-driven feedback mechanism rather than static batch processing.",
                "why_it_improves_uniqueness": "Most student projects stop at basic CRUD; reactive or adaptive systems stand out significantly in evaluations.",
                "implementation_hint": "Use WebSockets or Redis pub/sub with lightweight threshold scoring.",
                "difficulty": "Medium"
            },
            {
                "title": "Incorporate Privacy-Preserving or Edge Processing",
                "suggested_direction": "Run inference or sensitive filtering directly on client/edge devices.",
                "why_it_improves_uniqueness": "Data governance and low-latency local processing are current industry standards rarely seen in student submissions.",
                "implementation_hint": "Deploy ONNX Runtime Web or TensorFlow Lite on the client device.",
                "difficulty": "High"
            },
            {
                "title": "Automated Benchmark & Comparative Metrics Export",
                "suggested_direction": "Allow users to benchmark performance metrics against baseline standards with automated PDF reports.",
                "why_it_improves_uniqueness": "Transforms a single-purpose utility into an analytical tool suitable for academic research papers.",
                "implementation_hint": "Use ReportLab / Weasyprint combined with statistical aggregations.",
                "difficulty": "Low"
            }
        ]

        # Formulate external entries
        external_formatted = []
        for ext in external_evidence:
            external_formatted.append({
                "title": ext.get("title"),
                "source_type": ext.get("source_type"),
                "url": ext.get("url"),
                "summary": ext.get("description"),
                "relation_to_student_project": f"Public prior art in the same domain ({ext.get('query_used', 'general')})."
            })

        # Formulate internal entries
        internal_formatted = []
        for intr in internal_comparisons:
            internal_formatted.append({
                "project_name": intr.get("project_name"),
                "domain": intr.get("domain"),
                "shared_aspects": ", ".join(intr.get("shared_technologies", [])) or "Technical domain",
                "differentiation_note": intr.get("similarity_reason")
            })

        return {
            "project_summary": f"'{title}' is designed to solve: {problem[:120] if problem else desc[:120] or 'academic challenges'}.",
            "differentiation_score": score,
            "innovation_level": level,
            "score_rationale": rationale,
            "what_already_exists": existing,
            "potentially_unique_aspects": unique_aspects,
            "similar_external_projects": external_formatted,
            "similar_internal_projects": internal_formatted,
            "improvement_suggestions": improvements,
            "final_verdict": f"The proposal demonstrates solid foundations. Adopting at least two suggested architectural improvements will position '{title}' strongly for academic defense and capstone exhibitions.",
            "disclaimer": "This analysis is an AI-assisted evaluation based on public code repositories and internal database comparisons. It does not constitute a formal patent search or guarantee global novelty."
        }

    # =========================================================================
    # 7. VALIDATION & SANITIZATION
    # =========================================================================
    def _sanitize_and_validate_report(
        self,
        report: Dict[str, Any],
        external_evidence: List[Dict[str, Any]],
        internal_comparisons: List[Dict[str, Any]],
        title: str
    ) -> Dict[str, Any]:
        """Ensures all fields match contract, scores are valid, and URLs are verified."""
        # Sanitize score
        score = report.get("differentiation_score", 55)
        try:
            score = int(score)
        except Exception:
            score = 55
        score = max(5, min(95, score))
        report["differentiation_score"] = score

        # Level mapping
        if score < 40:
            level = "Low"
        elif score < 70:
            level = "Moderate"
        elif score < 85:
            level = "Good"
        else:
            level = "High"
        report["innovation_level"] = level

        # Summary
        if not report.get("project_summary"):
            report["project_summary"] = f"Proposed project '{title}' provides solutions for targeted domain workflows."

        # Arrays
        if not isinstance(report.get("what_already_exists"), list) or not report["what_already_exists"]:
            report["what_already_exists"] = ["Common application boilerplate and database schema structures."]

        if not isinstance(report.get("potentially_unique_aspects"), list) or not report["potentially_unique_aspects"]:
            report["potentially_unique_aspects"] = ["Specific combination of problem space and target user workflows."]

        # Ensure real external projects are populated with verified URLs
        if external_evidence:
            report_ext_urls = {
                e.get("url") for e in report.get("similar_external_projects", [])
                if isinstance(e, dict) and e.get("url")
            }
            # If AI omitted verified items or changed URLs, reinforce authentic evidence
            verified_list = []
            for ext in external_evidence:
                url = ext.get("url")
                # Find matching note from AI if present
                ai_match = next((item for item in report.get("similar_external_projects", []) if isinstance(item, dict) and item.get("url") == url), None)
                relation = ai_match.get("relation_to_student_project") if ai_match else f"Public solution in related domain ({ext.get('query_used', 'general')})."
                verified_list.append({
                    "title": ext.get("title"),
                    "source_type": ext.get("source_type"),
                    "url": url,
                    "summary": ext.get("description"),
                    "relation_to_student_project": relation
                })
            report["similar_external_projects"] = verified_list
        else:
            report["similar_external_projects"] = []

        # Internal projects
        if internal_comparisons and not report.get("similar_internal_projects"):
            report["similar_internal_projects"] = [
                {
                    "project_name": p.get("project_name"),
                    "domain": p.get("domain"),
                    "shared_aspects": ", ".join(p.get("shared_technologies", [])) or "Technical concepts",
                    "differentiation_note": p.get("similarity_reason")
                }
                for p in internal_comparisons
            ]

        # Improvements
        if not isinstance(report.get("improvement_suggestions"), list):
            report["improvement_suggestions"] = []

        if not report["improvement_suggestions"]:
            report["improvement_suggestions"] = [
                {
                    "title": "Contextual Automation / Reactive Engine",
                    "suggested_direction": "Incorporate automated alerts or event-driven triggers.",
                    "why_it_improves_uniqueness": "Moves the project beyond static forms into proactive systems.",
                    "implementation_hint": "Implement background worker queue or webhooks.",
                    "difficulty": "Medium"
                },
                {
                    "title": "Comprehensive Evaluation & Benchmarking",
                    "suggested_direction": "Add objective measurement and automated benchmark exports.",
                    "why_it_improves_uniqueness": "Provides empirical validation of project efficacy.",
                    "implementation_hint": "Generate quantitative performance logs with exportable metrics.",
                    "difficulty": "Low"
                }
            ]

        # Always enforce explicit disclaimer
        report["disclaimer"] = (
            "This analysis is an AI-assisted evaluation based on public code repositories and internal database comparisons. "
            "It does not constitute a formal patent search or guarantee global novelty."
        )

        return report

    # =========================================================================
    # 8. COMPLETE PIPELINE EXECUTION
    # =========================================================================
    def execute_analysis_pipeline(
        self,
        student_id: int,
        project_data: Dict[str, Any],
        use_cache: bool = True
    ) -> ProjectAnalysis:
        """
        Executes full innovation analysis workflow:
        1. Checks SHA-256 cache
        2. Generates queries
        3. Fetches external public evidence (GitHub + arXiv)
        4. Matches internal projects with privacy safeguards
        5. Analyzes with Gemini / AI
        6. Persists and returns ProjectAnalysis model
        """
        input_hash = self.compute_input_hash(project_data)

        # 1. Cache check
        if use_cache:
            existing_record = ProjectAnalysis.query.filter_by(
                student_id=student_id,
                input_hash=input_hash
            ).order_by(ProjectAnalysis.created_at.desc()).first()

            if existing_record:
                logger.info(f"Returning cached ProjectAnalysis {existing_record.id} for input hash {input_hash[:8]}")
                return existing_record

        # 2. Query formulation
        title = (project_data.get("project_title") or "").strip()
        problem = (project_data.get("problem_statement") or "").strip()
        desc = (project_data.get("project_description") or "").strip()
        sol = (project_data.get("proposed_solution") or "").strip()
        features = (project_data.get("main_features") or "").strip()
        tech = (project_data.get("technologies_used") or "").strip()
        users = (project_data.get("target_users") or "").strip()
        github = (project_data.get("github_url") or "").strip()
        notes = (project_data.get("additional_notes") or "").strip()

        queries = self.generate_search_queries(
            title=title,
            problem=problem,
            description=desc,
            solution=sol,
            features=features,
            technologies=tech,
            target_users=users
        )
        logger.info(f"Generated {len(queries)} search queries for project '{title}': {queries}")

        # 3. External public prior art search
        external_evidence = self.fetch_external_comparisons(queries)
        logger.info(f"Found {len(external_evidence)} external prior art items.")

        # 4. Internal campus comparisons
        internal_comparisons = self.find_similar_internal_projects(
            title=title,
            problem=problem,
            description=desc,
            technologies=tech
        )
        logger.info(f"Found {len(internal_comparisons)} similar internal projects.")

        # 5. Run AI analysis
        report = self.analyze_project_with_ai(
            project_data=project_data,
            external_evidence=external_evidence,
            internal_comparisons=internal_comparisons
        )

        score = report.get("differentiation_score", 50)
        level = report.get("innovation_level", "Moderate")

        # 6. Save to database
        analysis = ProjectAnalysis(
            student_id=student_id,
            project_title=title,
            problem_statement=problem,
            project_description=desc,
            proposed_solution=sol,
            main_features=features,
            technologies_used=tech,
            target_users=users,
            github_url=github,
            additional_notes=notes,
            input_hash=input_hash,
            differentiation_score=score,
            innovation_level=level,
            report_json=json.dumps(report, indent=2)
        )
        db.session.add(analysis)
        db.session.commit()

        logger.info(f"Created and saved ProjectAnalysis id={analysis.id} with score={score} ({level})")
        return analysis


# Global service instance
_analyzer_service_instance = None


def get_uniqueness_analyzer_service() -> UniquenessAnalyzerService:
    global _analyzer_service_instance
    if _analyzer_service_instance is None:
        _analyzer_service_instance = UniquenessAnalyzerService()
    return _analyzer_service_instance
