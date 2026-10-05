"""
AI PROJECT MENTOR SERVICE
=========================
Handles generative AI project analysis, automatic task breakdown,
missing/unnecessary task detection, blocker troubleshooting, smart check-ins,
and context-aware student mentoring.
"""

import json
import os
import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger("projexa.ai_service")


class AIService:
    def __init__(self):
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
        self.gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.api_key = os.environ.get("AI_API_KEY", "")
        self.model = os.environ.get("AI_MODEL", "gpt-4o-mini")
        self.base_url = os.environ.get("AI_BASE_URL", "")

    # =========================================================================
    # STAGE 1: DEEP PROJECT ANALYSIS & REQUIREMENTS EXTRACTION
    # =========================================================================
    def analyze_project_understanding(
        self,
        title: str,
        description: str,
        domain: str = "Web Development",
        technologies_known: str = "",
        team_size: int = 1,
        deadline_days: int = 60
    ) -> Dict[str, Any]:
        """
        Stage 1: Deep Project Analysis & Requirements Extraction.
        Extracts structured understanding (summary, type, features, users, tech, confidence).
        Identifies if project description is vague or underspecified and generates clarification questions.
        """
        logger.info(f"Stage 1 Project Analysis starting for: '{title}' (Domain: {domain})")

        # Check for trivially vague descriptions immediately
        desc_clean = (description or "").strip()
        words = [w for w in re.split(r"\s+", desc_clean) if w]
        is_too_brief = len(desc_clean) < 40 or len(words) < 6

        prompt = f"""You are an expert Senior Software Architect and Academic Project Guide.
Analyze the following student capstone / engineering project proposal:

PROJECT PROPOSAL:
- Title: {title}
- Description: {description}
- Domain: {domain}
- Technologies Known by Student: {technologies_known or "Standard web / database tools"}
- Team Size: {team_size} members
- Timeline Remaining: {deadline_days} days

TASK:
Deeply analyze the project proposal before generating any implementation tasks.
1. Determine if the description contains enough concrete information to build an accurate, project-specific technical roadmap.
   - If the description is too vague, generic, or brief (e.g., "Smart College System" with no specific features), set "clarification_required": true, set "confidence_score" between 40 and 75, and formulate 2 to 4 targeted, actionable clarification questions.
   - If sufficient details are provided, set "clarification_required": false and "confidence_score" between 80 and 100.
2. Extract the structured project understanding.

Return ONLY valid JSON matching this exact schema:
{{
  "project_summary": "Concise 2-sentence technical summary of the exact system requested.",
  "project_type": "Web Application",
  "domain": "{domain}",
  "core_objective": "Primary technical problem this project solves.",
  "required_features": [
    "Specific core feature 1",
    "Specific core feature 2",
    "Specific core feature 3"
  ],
  "optional_features": [
    "Nice-to-have extension 1"
  ],
  "expected_users": [
    "Primary User Role (e.g. Student, Teacher, Admin)"
  ],
  "technologies": [
    "Confirmed Tech 1", "Confirmed Tech 2"
  ],
  "required_data": [
    "Dataset or inputs needed, if any"
  ],
  "required_integrations": [
    "External API or hardware interface if needed"
  ],
  "technology_difficulty": "Medium",
  "confidence_score": 85,
  "clarification_required": false,
  "clarification_questions": []
}}
"""
        parsed = None
        if self.gemini_key:
            try:
                res_text = self._call_gemini_api(prompt)
                parsed = self._extract_json(res_text)
            except Exception as e:
                logger.warning(f"Gemini API error during Stage 1: {e}")

        if not parsed and self.api_key:
            try:
                res_text = self._call_llm(prompt)
                parsed = self._extract_json(res_text)
            except Exception as e:
                logger.warning(f"External LLM error during Stage 1: {e}")

        if not parsed or not isinstance(parsed, dict) or "required_features" not in parsed:
            parsed = self._generate_rule_based_project_understanding(title, description, domain, technologies_known, team_size)

        # Ensure title, description and domain are saved in understanding
        parsed["title"] = title
        parsed["description"] = description
        parsed["domain"] = domain or parsed.get("domain", "Web Development")

        # Programmatic guardrail for vague descriptions
        if is_too_brief:
            parsed["confidence_score"] = min(float(parsed.get("confidence_score", 60)), 65.0)
            parsed["clarification_required"] = True
            if not parsed.get("clarification_questions"):
                parsed["clarification_questions"] = [
                    f"What are the main features and actions users will perform in '{title}'?",
                    "Who will use the system (e.g., students, teachers, administrators, public)?",
                    "Is this a web application, mobile app, machine learning pipeline, or IoT hardware system?"
                ]

        logger.info(f"Stage 1 Result: Confidence={parsed.get('confidence_score')}%, Clarification={parsed.get('clarification_required')}, Features={len(parsed.get('required_features', []))}")
        return parsed

    # =========================================================================
    # STAGE 2: REQUIREMENT-TO-TASK GENERATION WITH AI SELF-REVIEW
    # =========================================================================
    def generate_tasks_from_requirements(
        self,
        understanding: Dict[str, Any],
        custom_instructions: str = "",
        team_size: int = 1,
        deadline_days: int = 60
    ) -> Dict[str, Any]:
        """
        Stage 2: Requirement-to-Task Generation with AI Self-Review.
        Generates tasks mapped directly to validated requirements without generic placeholders.
        """
        title = understanding.get("title", "Project")
        domain = understanding.get("domain", "Web Development")
        proj_type = understanding.get("project_type", "Web Application")
        req_features = understanding.get("required_features", [])
        exp_users = understanding.get("expected_users", [])
        confirmed_tech = understanding.get("technologies", [])
        req_data = understanding.get("required_data", [])
        req_integrations = understanding.get("required_integrations", [])

        logger.info(f"Stage 2 Task Generation starting for: '{title}' ({len(req_features)} requirements)")

        prompt = f"""You are an expert Senior Technical Project Lead and Engineering Architect.
Stage 2: Generate an accurate, project-specific, technically rigorous development roadmap.

VALIDATED PROJECT REQUIREMENTS:
- Project Title: {title}
- Project Summary: {understanding.get("project_summary")}
- Project Type: {proj_type}
- Domain: {domain}
- Core Objective: {understanding.get("core_objective")}
- Required Features: {json.dumps(req_features)}
- Expected Users / Roles: {json.dumps(exp_users)}
- Technologies Selected: {json.dumps(confirmed_tech)}
- Required Datasets / Inputs: {json.dumps(req_data)}
- Required Integrations / APIs: {json.dumps(req_integrations)}
- Custom Student Instructions / Feedback: {custom_instructions or "None"}

CRITICAL GENERATION RULES:
1. ACCURACY & RELEVANCE FIRST: Every generated task must directly contribute to implementing a stated requirement or an unavoidable technical dependency.
2. REQUIREMENT MAPPING: Every task MUST specify "requirement_source" indicating the exact required feature, user role, or dependency it fulfills.
3. DO NOT ASSUME UNREQUESTED PLATFORMS OR FEATURES:
   - If this is a Web application, DO NOT generate mobile APK, Flutter, or React Native tasks.
   - If this is NOT a machine learning project, DO NOT generate model training, dataset labeling, or CNN tasks.
   - If payments are NOT requested, DO NOT generate Stripe, PayPal, or payment gateway tasks.
   - If user accounts/login are NOT requested, DO NOT generate authentication wireframes or password reset tasks.
4. NO GENERIC PLACEHOLDER TASKS:
   - NEVER generate vague tasks such as: "Develop the system", "Work on backend", "Create frontend", "Complete project", "Do testing".
   - Generate concrete, actionable milestones (e.g., "Build audio capture controller using Web Speech API", "Design SQLite schema for Student Attendance records").
5. DYNAMIC DOMAIN-SPECIFIC PHASES:
   Organize tasks into 5 to 6 logical phases that fit the project domain:
   * For Web / Software: Phase 1 — Research & Requirement Specification, Phase 2 — UI/UX Wireframing & Design, Phase 3 — Core Feature & API Development, Phase 4 — Database Persistence & Schema Design, Phase 5 — Integration Testing & Quality Assurance, Phase 6 — Deployment & Academic Documentation.
   * For AI / Machine Learning: Phase 1 — Problem Definition & Data Sourcing, Phase 2 — Data Preprocessing & EDA, Phase 3 — Feature Engineering & Preprocessing Pipeline, Phase 4 — Model Architecture & Training, Phase 5 — Model Evaluation & Validation, Phase 6 — Deployment & Academic Report.
   * For IoT / Hardware: Phase 1 — Architecture & Component Selection, Phase 2 — Circuit Design & Schematic, Phase 3 — Firmware & Sensor Interfacing, Phase 4 — Cloud & Data Integration, Phase 5 — Hardware Testing & Validation, Phase 6 — Project Documentation & Defense.
6. AI SELF-REVIEW:
   Review all generated tasks against the requirements. Strip any task that is an assumption, unrelated, or unrequested.

Return ONLY valid JSON matching this schema:
{{
  "system_architecture": "Concise architectural design description for this project.",
  "phases": [
    {{
      "phase_number": 1,
      "name": "Phase 1 — <Domain Appropriate Name>",
      "tasks": [
        {{
          "title": "Specific, actionable task title",
          "description": "Clear explanation of technical implementation",
          "priority": "Critical" or "High" or "Medium" or "Low" or "Optional",
          "category": "Backend" or "Frontend" or "Database" or "Machine Learning" or "Hardware" or "Testing" or "Documentation" or "Research" or "Deployment",
          "difficulty": "Easy" or "Medium" or "Hard",
          "estimated_hours": 4.0,
          "can_parallel": true,
          "dependencies": [],
          "requirement_source": "Exact required feature this task satisfies",
          "reason": "Why this specific task is technically required"
        }}
      ]
    }}
  ],
  "ai_tools": [
    {{
      "stage": "Phase Name",
      "tool_name": "Tool Name",
      "purpose": "Purpose for this specific project",
      "ready_to_use_prompt": "Specific copyable prompt for this project"
    }}
  ],
  "suggested_technologies": ["Tech 1", "Tech 2", "Tech 3"],
  "parallel_tasks_advice": "Advice for concurrent execution"
}}
"""
        parsed = None
        if self.gemini_key:
            try:
                res_text = self._call_gemini_api(prompt)
                parsed = self._extract_json(res_text)
            except Exception as e:
                logger.warning(f"Gemini API error during Stage 2: {e}")

        if not parsed and self.api_key:
            try:
                res_text = self._call_llm(prompt)
                parsed = self._extract_json(res_text)
            except Exception as e:
                logger.warning(f"External LLM error during Stage 2: {e}")

        if not parsed or not isinstance(parsed, dict) or "phases" not in parsed or len(parsed.get("phases", [])) < 3:
            parsed = self._generate_rule_based_tasks_from_requirements(understanding, custom_instructions, team_size)

        # Sanitize and validate every task through the programmatic validation layer
        all_tasks = []
        for phase in parsed.get("phases", []):
            for t in phase.get("tasks", []):
                t["phase"] = phase.get("name", "Phase 1 — Research & Planning")
                t["phase_number"] = phase.get("phase_number", 1)
                all_tasks.append(t)

        validated_tasks = self.validate_and_sanitize_tasks(all_tasks, understanding)

        # Re-group validated tasks by phase
        phases_map = {}
        for t in validated_tasks:
            p_name = t.get("phase", "Phase 1 — Research & Planning")
            p_num = t.get("phase_number", 1)
            if p_name not in phases_map:
                phases_map[p_name] = {
                    "phase_number": p_num,
                    "name": p_name,
                    "tasks": []
                }
            phases_map[p_name]["tasks"].append(t)

        parsed["phases"] = sorted(phases_map.values(), key=lambda x: x["phase_number"])
        return self._enrich_plan_response(parsed, title, domain)

    # =========================================================================
    # BACKEND TASK VALIDATION LAYER
    # =========================================================================
    def validate_and_sanitize_tasks(
        self,
        tasks: List[Dict[str, Any]],
        understanding: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Backend Programmatic Validation Layer:
        1. Anti-generic filter (rejects vague placeholders like 'Develop the system')
        2. Relevance & contradiction filter (strips unrequested mobile, ML, payment, auth)
        3. Deduplication filter (eliminates duplicate titles or high token overlap)
        4. Dependency integrity (removes circular/self/non-existent dependencies)
        5. Requirement mapping enforcement (ensures requirement_source is present)
        """
        title = understanding.get("title", "")
        domain = understanding.get("domain", "")
        proj_type = understanding.get("project_type", "")
        summary = understanding.get("project_summary", "")
        req_features = understanding.get("required_features", [])

        full_context = f"{title} {domain} {proj_type} {summary} {' '.join(req_features)}".lower()

        is_mobile = proj_type == "Mobile Application" or "mobile" in domain.lower() or any(w in full_context for w in ["mobile", "android", "ios", "flutter", "react native", "smartphone", "apk"])
        is_ml = "machine learning" in domain.lower() or "ai" in domain.lower() or any(w in full_context for w in ["machine learning", "deep learning", "neural", "nlp", "computer vision", "predict", "classifier", "model training", "dataset"])
        is_payment = any(w in full_context for w in ["payment", "stripe", "paypal", "credit card", "razorpay", "billing", "checkout fee", "subscription"])
        is_auth = any(w in full_context for w in ["login", "auth", "user", "student", "teacher", "admin", "account", "register", "password", "role", "portal", "profile"])

        generic_exact = {
            "develop the system", "work on backend", "create frontend", "complete project",
            "do testing", "implement features", "start project", "build application",
            "do coding", "test system", "make frontend", "finish project", "build the entire application",
            "develop backend", "setup project", "project development", "coding", "testing phase"
        }

        sanitized = []
        seen_titles = set()

        for t in tasks:
            raw_title = (t.get("title") or t.get("task_title") or "").strip()
            if not raw_title:
                continue

            title_clean = raw_title.lower()

            # 1. Anti-Generic Check
            if title_clean in generic_exact:
                logger.warning(f"Task validation REJECTED generic task: '{raw_title}'")
                continue

            # 2. Contradiction Checks
            # Mobile contradiction
            if not is_mobile and any(m in title_clean for m in ["react native", "android apk", "ios app", "app store", "play store", "flutter mobile", "build apk"]):
                logger.warning(f"Task validation REJECTED unrequested mobile task for non-mobile project: '{raw_title}'")
                continue

            # ML contradiction
            if not is_ml and any(m in title_clean for m in ["train machine learning", "train cnn", "train deep learning", "train neural network", "convolutional neural", "epoch loss", "hyperparameter tuning", "scikit-learn pipeline"]):
                logger.warning(f"Task validation REJECTED unrequested ML training task for non-ML project: '{raw_title}'")
                continue

            # Payment contradiction
            if not is_payment and any(p in title_clean for p in ["stripe", "paypal", "razorpay", "payment gateway", "credit card"]):
                logger.warning(f"Task validation REJECTED unrequested payment task for non-payment project: '{raw_title}'")
                continue

            # Auth contradiction
            if not is_auth and any(a in title_clean for a in ["jwt authentication", "user password reset", "oauth2 login", "login, registration"]):
                logger.warning(f"Task validation REJECTED unrequested authentication task: '{raw_title}'")
                continue

            # 3. Deduplication Check
            tokens = set(re.findall(r"\w+", title_clean))
            is_dup = False
            for seen in seen_titles:
                seen_tokens = set(re.findall(r"\w+", seen))
                intersection = tokens.intersection(seen_tokens)
                union = tokens.union(seen_tokens)
                jaccard = len(intersection) / len(union) if union else 0
                if title_clean == seen or (jaccard > 0.82 and len(tokens) > 2):
                    is_dup = True
                    break

            if is_dup:
                logger.warning(f"Task validation REJECTED duplicate task: '{raw_title}'")
                continue

            seen_titles.add(title_clean)

            # 4. Requirement Source Assignment
            req_source = t.get("requirement_source", "").strip()
            if not req_source or req_source.lower() in ["none", "general", "n/a"]:
                if req_features:
                    best_match = req_features[0]
                    best_score = 0
                    for feat in req_features:
                        f_tokens = set(re.findall(r"\w+", feat.lower()))
                        score = len(tokens.intersection(f_tokens))
                        if score > best_score:
                            best_score = score
                            best_match = feat
                    t["requirement_source"] = best_match
                else:
                    t["requirement_source"] = understanding.get("core_objective", "Core project deliverable")

            sanitized.append(t)

        # 5. Dependency Validation (remove references to tasks that do not exist or self-references)
        valid_titles = {s["title"] for s in sanitized}
        for s in sanitized:
            deps = s.get("dependencies") or []
            if isinstance(deps, list):
                clean_deps = [d for d in deps if d in valid_titles and d != s["title"]]
                s["dependencies"] = clean_deps

        logger.info(f"Task Validation: {len(tasks)} candidate tasks -> {len(sanitized)} valid sanitized tasks")
        return sanitized

    # =========================================================================
    # UNIFIED PIPELINE WRAPPER (BACKWARD COMPATIBILITY)
    # =========================================================================
    def analyze_project_and_generate_tasks(
        self,
        title: str,
        description: str,
        domain: str = "Web Development",
        technologies_known: str = "",
        team_size: int = 1,
        deadline_days: int = 60
    ) -> Dict[str, Any]:
        """
        Two-step workflow:
        Stage 1: Project understanding, requirement extraction, confidence score, clarification check.
        Stage 2: Requirement-to-task generation with self-review and backend validation.
        """
        understanding = self.analyze_project_understanding(
            title=title,
            description=description,
            domain=domain,
            technologies_known=technologies_known,
            team_size=team_size,
            deadline_days=deadline_days
        )

        plan = self.generate_tasks_from_requirements(
            understanding=understanding,
            custom_instructions="",
            team_size=team_size,
            deadline_days=deadline_days
        )

        # Merge Stage 1 understanding details into plan
        plan["project_analysis"] = understanding
        plan["confidence_score"] = understanding.get("confidence_score", 90.0)
        plan["clarification_required"] = understanding.get("clarification_required", False)
        plan["clarification_questions"] = understanding.get("clarification_questions", [])
        plan["project_type"] = understanding.get("project_type", "Web Application")
        plan["main_objective"] = understanding.get("core_objective", "")
        plan["project_summary"] = understanding.get("project_summary", "")

        return plan

    def detect_missing_tasks(self, project, current_tasks: List[Any]) -> List[Dict[str, Any]]:
        """
        Scans current tasks against project requirements to find overlooked essential tasks
        (e.g., testing, validation, error handling, documentation, deployment).
        """
        task_titles = [t.title.lower() if hasattr(t, 'title') else t.get('title', '').lower() for t in current_tasks]
        task_categories = [t.category.lower() if hasattr(t, 'category') else t.get('category', '').lower() for t in current_tasks]
        all_text = " ".join(task_titles) + " " + " ".join(task_categories)

        missing = []

        # 1. Testing Check
        if "test" not in all_text and "unit" not in all_text and "qa" not in all_text:
            missing.append({
                "title": "Implement Unit & Integration Tests",
                "category": "Testing",
                "priority": "High",
                "difficulty": "Medium",
                "reason": "No testing tasks detected. Automated test suites prevent breaking core modules near the submission deadline."
            })

        # 2. Database/Validation
        if "validat" not in all_text and "error" not in all_text and "security" not in all_text:
            missing.append({
                "title": "Input Validation & Error Handling Middleware",
                "category": "Backend",
                "priority": "High",
                "difficulty": "Easy",
                "reason": "Robust input sanitization prevents crashes during live faculty evaluation."
            })

        # 3. Documentation
        if "doc" not in all_text and "report" not in all_text and "manual" not in all_text:
            missing.append({
                "title": "Draft Academic Project Report & Architecture Diagrams",
                "category": "Documentation",
                "priority": "High",
                "difficulty": "Medium",
                "reason": "Final thesis/capstone documentation accounts for a significant portion of academic evaluation."
            })

        # 4. Presentation / Demo Prep
        if "presentation" not in all_text and "demo" not in all_text and "slides" not in all_text:
            missing.append({
                "title": "Presentation Slides & Live Demo Rehearsal",
                "category": "Presentation",
                "priority": "Medium",
                "difficulty": "Easy",
                "reason": "Rehearsing the viva demo with a pre-recorded backup video ensures smooth evaluation."
            })

        # 5. Domain specific checks
        desc_lower = (project.description or "").lower()
        if ("machine learning" in desc_lower or "ai" in desc_lower or "model" in desc_lower) and "evaluat" not in all_text:
            missing.append({
                "title": "Model Evaluation & Confusion Matrix Diagnostics",
                "category": "Machine Learning",
                "priority": "Critical",
                "difficulty": "Medium",
                "reason": "Evaluation metrics (Accuracy, Precision, Recall, F1) are essential to justify ML project validity."
            })

        return missing

    def detect_unnecessary_tasks(self, project, current_tasks: List[Any]) -> List[Dict[str, Any]]:
        """
        Identifies tasks that might be low-priority or feature-creep distractions.
        """
        flagged = []
        low_priority_keywords = [
            "animation", "3d", "dark mode", "sound effect", "easter egg",
            "social media sharing", "multi-language support", "complex styling",
            "custom mascot", "virtual reality", "gamification"
        ]

        for t in current_tasks:
            raw_title = t.title if hasattr(t, 'title') else t.get('title', '')
            raw_desc = t.description if hasattr(t, 'description') else t.get('description', '')
            title = (raw_title or "").lower()
            desc = (raw_desc or "").lower()
            
            for kw in low_priority_keywords:
                if kw in title or kw in desc:
                    flagged.append({
                        "task_id": t.id if hasattr(t, 'id') else None,
                        "title": raw_title,
                        "reason": f"Contains '{kw}' which does not contribute to the core academic deliverable and may consume critical time."
                    })
                    break

        return flagged

    def evaluate_additional_task(self, project, task_title: str, existing_tasks: List[Any]) -> Dict[str, Any]:
        """
        Evaluates a new task submitted by the student to determine categorization,
        priority, and whether it duplicates an existing item.
        """
        title_clean = task_title.strip().lower()

        # Check for duplicates / high similarity
        duplicate_found = None
        for t in existing_tasks:
            existing_title = (t.title if hasattr(t, 'title') else t.get('title', '')).strip().lower()
            if title_clean == existing_title or (len(title_clean) > 8 and title_clean in existing_title):
                duplicate_found = t.title if hasattr(t, 'title') else t.get('title', '')
                break

        # Categorize
        category = "Backend"
        priority = "High"
        if any(w in title_clean for w in ["ui", "frontend", "css", "html", "react", "page", "view"]):
            category = "Frontend"
        elif any(w in title_clean for w in ["database", "sql", "table", "schema", "mongo", "db"]):
            category = "Database"
            priority = "Critical"
        elif any(w in title_clean for w in ["test", "unittest", "integration", "coverage", "qa"]):
            category = "Testing"
        elif any(w in title_clean for w in ["doc", "report", "diagram", "manual"]):
            category = "Documentation"
        elif any(w in title_clean for w in ["ai", "model", "ml", "train", "dataset", "neural"]):
            category = "Machine Learning"
        elif any(w in title_clean for w in ["deploy", "docker", "cloud", "aws", "server"]):
            category = "Deployment"

        return {
            "title": task_title.strip(),
            "category": category,
            "priority": priority,
            "difficulty": "Medium",
            "is_duplicate": duplicate_found is not None,
            "duplicate_of": duplicate_found,
            "message": f"Task appears similar to existing task '{duplicate_found}'." if duplicate_found else "Valid task added to project plan."
        }

    def run_ai_project_checkin(self, project, tasks: List[Any], days_remaining: int) -> Dict[str, Any]:
        """
        Generates a comprehensive AI Smart Check-In assessment, health breakdown,
        and prioritized next steps.
        """
        total = len(tasks)
        completed = sum(1 for t in tasks if (t.status if hasattr(t, 'status') else t.get('status')) == "Completed")
        blocked = sum(1 for t in tasks if (t.status if hasattr(t, 'status') else t.get('status')) == "Blocked")
        in_progress = sum(1 for t in tasks if (t.status if hasattr(t, 'status') else t.get('status')) == "In Progress")
        pending = total - completed

        progress_pct = round((completed / max(1, total)) * 100.0, 1)

        # Recommendations
        recs = []
        if blocked > 0:
            recs.append(f"Resolve the {blocked} blocked task(s) immediately by requesting assistance or reviewing error logs.")
        
        # Check testing
        has_testing_done = any(
            (t.category if hasattr(t, 'category') else t.get('category')) == "Testing" and 
            (t.status if hasattr(t, 'status') else t.get('status')) == "Completed"
            for t in tasks
        )
        if not has_testing_done:
            recs.append("Initiate unit and integration testing on completed modules before adding new features.")

        if days_remaining <= 14 and pending > 4:
            recs.append("Triage non-core deliverables to ensure a working prototype is ready for the deadline.")
        else:
            recs.append("Maintain steady daily task velocity and draft project report documentation in parallel.")

        summary = f"Project is currently at {progress_pct}% completion ({completed}/{total} tasks done). "
        if blocked > 0:
            summary += f"Attention needed: {blocked} task(s) are currently marked as Blocked. "
        if days_remaining <= 14:
            summary += f"Timeline is tightening with {days_remaining} days remaining until evaluation."
        else:
            summary += f"Timeline is manageable with {days_remaining} days remaining."

        return {
            "progress_percentage": progress_pct,
            "total_tasks": total,
            "completed_tasks": completed,
            "in_progress_tasks": in_progress,
            "blocked_tasks": blocked,
            "pending_tasks": pending,
            "days_remaining": days_remaining,
            "ai_summary": summary,
            "recommendations": recs
        }

    def answer_mentor_question(self, project, question: str, tasks: List[Any], days_remaining: int) -> str:
        """
        Answers student mentoring questions using full live project context.
        """
        total = len(tasks)
        completed = [t.title if hasattr(t, 'title') else t.get('title') for t in tasks if (t.status if hasattr(t, 'status') else t.get('status')) == "Completed"]
        blocked = [t.title if hasattr(t, 'title') else t.get('title') for t in tasks if (t.status if hasattr(t, 'status') else t.get('status')) == "Blocked"]
        pending = [t.title if hasattr(t, 'title') else t.get('title') for t in tasks if (t.status if hasattr(t, 'status') else t.get('status')) in ["Not Started", "In Progress"]]

        prompt = f"""You are Projexa's intelligent AI Project Mentor.
Answer the student's question accurately using their specific project context.

PROJECT TITLE: {project.project_name}
DESCRIPTION: {project.description}
DOMAIN: {project.domain}
DAYS REMAINING: {days_remaining}
TOTAL TASKS: {total}
COMPLETED TASKS: {', '.join(completed[:5]) if completed else 'None yet'}
BLOCKED TASKS: {', '.join(blocked) if blocked else 'None'}
PENDING TASKS: {', '.join(pending[:6]) if pending else 'None'}

STUDENT QUESTION: {question}

Provide a supportive, concise, practical, and direct engineering response. (Max 3 paragraphs).
"""
        if self.api_key:
            try:
                res = self._call_llm(prompt)
                if res and len(res.strip()) > 10:
                    return res.strip()
            except Exception as e:
                print(f"[-] Mentor chat LLM error: {e}")

        # Intelligent contextual fallback
        q_lower = question.lower()
        if "first" in q_lower or "next" in q_lower or "start" in q_lower:
            if blocked:
                return f"I recommend addressing your blocked task **'{blocked[0]}'** first before taking on new work. Unblocking foundation modules keeps your timeline healthy."
            elif pending:
                return f"Your next priority should be **'{pending[0]}'**. Completing core functional modules will give you a working prototype for demonstration."
            return "All current tasks appear completed! Focus on edge-case testing, performance optimization, and final report documentation."

        elif "risk" in q_lower or "why" in q_lower:
            reasons = []
            if blocked:
                reasons.append(f"{len(blocked)} task(s) are blocked")
            if days_remaining <= 14:
                reasons.append(f"only {days_remaining} days remain")
            if len(completed) < len(pending):
                reasons.append(f"more than half of planned tasks ({len(pending)}) are still pending")
            
            reason_str = ", ".join(reasons) if reasons else "schedule pacing"
            return f"Your project risk is calculated based on milestone pacing: {reason_str}. You can lower your risk by unblocking pending tasks and logging testing progress."

        elif "missing" in q_lower:
            return "Based on your project architecture, ensure you have tasks for **Unit/Integration Testing**, **Input Validation**, and **Final Documentation Report**."

        elif "remove" in q_lower or "optional" in q_lower:
            return "You can safely mark non-essential visual enhancements (such as dark mode toggles or complex landing page animations) as 'Optional' if you need to prioritize core functionality."

        return f"For **{project.project_name}**, focus on completing core deliverables first ({len(completed)}/{total} completed). Keep your tests updated and maintain regular documentation alongside code development."

    def troubleshoot_blocker(self, task_title: str, blocker_reason: str) -> str:
        """
        Provides actionable troubleshooting steps when a student marks a task as Blocked.
        """
        b_lower = blocker_reason.lower()
        if "database" in b_lower or "connection" in b_lower:
            return "1. Verify your database connection string and credentials in `.env`.\n2. Ensure the local/remote DB server is running (`pg_isready` / `systemctl status`).\n3. Check firewall and port binding permissions."
        elif "cors" in b_lower or "api" in b_lower:
            return "1. Ensure CORS middleware is enabled on your backend (`Flask-CORS` / Express `cors`).\n2. Verify the frontend API base URL matches the backend port.\n3. Inspect browser developer tools Network tab for 403/404 headers."
        elif "package" in b_lower or "import" in b_lower or "module" in b_lower:
            return "1. Ensure your active Python virtual environment is activated (`venv\\Scripts\\activate`).\n2. Run `pip install -r requirements.txt`.\n3. Check for circular imports between module files."
        
        return f"To unblock **{task_title}**:\n1. Inspect exact error logs and stack traces.\n2. Break the problem into isolated unit tests.\n3. Check official framework documentation or consult your faculty mentor."

    def regenerate_project_tasks(self, project, instructions: str = "") -> Dict[str, Any]:
        """
        Regenerates tasks for an existing project using validated project understanding
        combined with student modification instructions.
        Honors student constraints (e.g., 'remove machine learning tasks', 'remove payment').
        """
        logger.info(f"Regenerating tasks for project {project.id} with instructions: '{instructions}'")
        understanding = project.get_requirements()
        if not understanding or not understanding.get("required_features"):
            understanding = self.analyze_project_understanding(
                title=project.project_name,
                description=project.description,
                domain=project.domain,
                technologies_known=project.technologies_known or "",
                team_size=project.team_size
            )

        # Apply student negative constraints to requirements
        instr_lower = (instructions or "").lower()
        req_features = list(understanding.get("required_features", []))

        if any(w in instr_lower for w in ["remove machine learning", "no ml", "no ai", "remove ml", "remove ai"]):
            req_features = [f for f in req_features if not any(w in f.lower() for w in ["ml", "machine learning", "ai model", "neural", "predict", "classifier", "train model"])]
            understanding["domain"] = "Web Development"
            understanding["project_type"] = "Web Application"

        if any(w in instr_lower for w in ["remove payment", "no payment"]):
            req_features = [f for f in req_features if not any(w in f.lower() for w in ["payment", "stripe", "paypal", "billing", "checkout", "fee"])]

        if any(w in instr_lower for w in ["remove mobile", "no mobile"]):
            req_features = [f for f in req_features if not any(w in f.lower() for w in ["mobile", "android", "ios", "apk", "flutter", "react native"])]

        if any(w in instr_lower for w in ["remove auth", "no auth", "remove login"]):
            req_features = [f for f in req_features if not any(w in f.lower() for w in ["auth", "login", "password", "session", "jwt", "registration"])]

        # If instructions add specific feature requests
        if "security" in instr_lower and not any("security" in f.lower() for f in req_features):
            req_features.append("Security hardening, input sanitization, and automated vulnerability scanning")
        if "ci/cd" in instr_lower or "pipeline" in instr_lower:
            req_features.append("Automated CI/CD deployment pipeline and integration tests")

        understanding["required_features"] = req_features

        plan = self.generate_tasks_from_requirements(
            understanding=understanding,
            custom_instructions=instructions,
            team_size=project.team_size
        )
        plan["project_analysis"] = understanding
        return plan

    def analyze_progress_and_guidance(self, project, tasks: List[Any]) -> Dict[str, Any]:
        """
        Analyzes live task progress vs timeline and provides:
        - Timeline pacing warning (e.g., completed 30% tasks, but 60% timeline passed)
        - Prioritized next tasks
        - Parallelizable tasks
        - Blocked tasks resolution advice
        - Missing tasks
        - Recommended system architecture
        """
        pacing = project.get_timeline_pacing()
        
        # Categorize tasks
        not_started = [t for t in tasks if getattr(t, 'status', '') == 'Not Started']
        in_progress = [t for t in tasks if getattr(t, 'status', '') == 'In Progress']
        completed = [t for t in tasks if getattr(t, 'status', '') == 'Completed']
        blocked = [t for t in tasks if getattr(t, 'status', '') == 'Blocked']
        
        # Determine prioritized next tasks
        prioritized = []
        if blocked:
            for b in blocked[:2]:
                prioritized.append({
                    "task": b,
                    "reason": "CRITICAL: Unblocking this task is required before dependent features can proceed.",
                    "urgency": "Urgent"
                })
        
        for ip in in_progress[:2]:
            prioritized.append({
                "task": ip,
                "reason": "HIGH: Currently active work. Finish this to advance project completion ratio.",
                "urgency": "High"
            })
            
        for ns in [t for t in not_started if getattr(t, 'priority', '') in ['Critical', 'High']][:3]:
            if len(prioritized) < 4:
                prioritized.append({
                    "task": ns,
                    "reason": f"FOUNDATIONAL: {getattr(ns, 'category', 'Core')} milestone required for core academic evaluation.",
                    "urgency": "High"
                })
                
        # Determine parallel tasks
        parallel_tasks = [t for t in not_started if getattr(t, 'can_parallel', False) or getattr(t, 'category', '') in ['Testing', 'Documentation', 'Frontend']]
        
        missing = self.detect_missing_tasks(project, tasks)
        
        return {
            "pacing": pacing,
            "prioritized_tasks": prioritized,
            "parallel_tasks": parallel_tasks[:4],
            "blocked_tasks": blocked,
            "missing_tasks": missing,
            "architecture": project.architecture_recommendation or "Modern modular three-tier client-server architecture with REST API integration."
        }

    def get_project_structured_analysis(self, project, tasks: List[Any] = None) -> Dict[str, Any]:
        """
        Synthesizes the complete 9-section structured AI Project Analysis for the student:
        1. Overview
        2. What to Build
        3. Tools to Use
        4. How It Works
        5. Database
        6. Development Plan
        7. Tasks
        8. Testing
        9. Security
        All written in simple, clear, student-friendly English without technical jargon.
        """
        if tasks is None:
            tasks = project.tasks.all()

        req = project.get_requirements()
        title = project.project_name
        desc = project.description or ""
        domain = project.domain or "Web Development"
        summary = project.project_summary or req.get("project_summary", "") or f"A helpful {domain} project that solves problems for students and teachers."
        objective = project.objective or req.get("core_objective", "") or f"Build a working system for {title}."
        tech_known = project.technologies_known or "Python, Web basics"
        diff = project.technology_difficulty or req.get("technology_difficulty", "Medium")

        # 1. Overview data
        est_effort_weeks = max(4, round(len(tasks) * 0.8)) if tasks else 6
        overview_data = {
            "title": title,
            "simple_description": desc or f"This is an academic project called {title} built to help users manage their work easily.",
            "problem": f"Before this project, users had to do these steps manually or use slow, complicated tools that take a lot of time.",
            "goal": objective,
            "ai_summary": summary,
            "difficulty_level": diff,
            "estimated_effort": f"Around {est_effort_weeks} weeks ({len(tasks) * 4 if tasks else 40} total study and coding hours)"
        }

        # 2. What to Build (Features with simple labels)
        raw_req_features = req.get("required_features", [])
        raw_opt_features = req.get("optional_features", [])
        expected_users = req.get("expected_users", ["Students", "Teachers / Admins"])

        features_list = []
        if raw_req_features:
            for i, feat in enumerate(raw_req_features):
                priority_label = "Must Have" if i < 3 else "Good to Have"
                badge_class = "danger" if priority_label == "Must Have" else "warning text-dark"
                features_list.append({
                    "name": feat,
                    "description": f"Core function that lets users complete their main task smoothly.",
                    "priority": priority_label,
                    "badge_class": badge_class,
                    "module": "Main Features"
                })
        else:
            features_list.append({
                "name": "User Sign-in and Account Management",
                "description": "Lets students and teachers log in safely with their own accounts.",
                "priority": "Must Have",
                "badge_class": "danger",
                "module": "User Accounts"
            })
            features_list.append({
                "name": f"Core Work Area for {title}",
                "description": "The main screen where users see their daily information, enter data, and view updates.",
                "priority": "Must Have",
                "badge_class": "danger",
                "module": "Main Work Area"
            })
            features_list.append({
                "name": "Reports and Information Summary",
                "description": "Shows quick counts, charts, and downloadable summaries for college evaluation.",
                "priority": "Good to Have",
                "badge_class": "warning text-dark",
                "module": "Reporting"
            })

        if raw_opt_features:
            for feat in raw_opt_features:
                features_list.append({
                    "name": feat,
                    "description": "Helpful extra feature you can add after your main features work properly.",
                    "priority": "Optional",
                    "badge_class": "secondary",
                    "module": "Extra Features"
                })

        modules_list = [
            {"name": "User Account Module", "purpose": "Handles user registration, login checks, and user roles."},
            {"name": "Core Work Module", "purpose": "Manages the primary activity and data records of the project."},
            {"name": "Reports & Dashboard Module", "purpose": "Presents summary cards, progress bars, and clean tables."}
        ]

        what_to_build_data = {
            "features": features_list,
            "modules": modules_list,
            "user_roles": expected_users,
            "total_features_count": len(features_list)
        }

        # 3. Tools to Use (with simple why explanations)
        tools_list = []
        # Frontend
        tools_list.append({
            "category": "Frontend (Screen Design)",
            "name": "HTML5, CSS3 & Bootstrap",
            "why": "It gives you clean buttons, boxes, and mobile-friendly screens without writing thousands of lines of style code from scratch."
        })
        # Backend
        backend_name = "Python (Flask)" if "flask" in (project.technologies or "").lower() or "python" in (project.technologies or "").lower() else "Python / Node.js"
        tools_list.append({
            "category": "Backend (Server Logic)",
            "name": backend_name,
            "why": "It runs your website logic, checks inputs, and talks safely to your database using easy-to-read code."
        })
        # Database
        tools_list.append({
            "category": "Database (Data Storage)",
            "name": "SQLite / PostgreSQL",
            "why": "It safely remembers your project records in organized tables so information stays saved even when your laptop restarts."
        })
        # APIs / Libraries
        tools_list.append({
            "category": "Libraries & Helper Tools",
            "name": "Chart.js & FontAwesome",
            "why": "They create beautiful interactive graphs for your teachers and add friendly icons to your buttons."
        })
        # Other tools
        tools_list.append({
            "category": "Project Helpers",
            "name": "Git & GitHub",
            "why": "Keeps a safe backup history of your project code so you can undo mistakes anytime."
        })

        # 4. How It Works (Simple flows and system architecture)
        how_it_works_data = {
            "system_flow": [
                {"step": 1, "title": "User Opens Website", "detail": "The student or teacher opens the app in any modern browser."},
                {"step": 2, "title": "Checks Who Is Logged In", "detail": "The system checks if the user is a student, teacher, or admin to show the right screen."},
                {"step": 3, "title": "Runs Project Action", "detail": "The user submits a form (e.g. marks attendance, adds a project task, or updates a record)."},
                {"step": 4, "title": "Saves in Database", "detail": "The backend server checks for errors and saves the record permanently into the database."},
                {"step": 5, "title": "Shows Updated Result", "detail": "The screen updates immediately with green success messages and new summary numbers."}
            ],
            "user_flow": f"User opens the app → Logs in → Views personal dashboard → Completes tasks → Views simple summary reports.",
            "data_flow": "Browser Screen → Backend Server Routes → Database Tables → Immediate Screen Feedback.",
            "simple_architecture": project.architecture_recommendation or "Three-tier architecture: 1) Easy web screen, 2) Python backend logic, 3) Safe relational database tables."
        }

        # 5. Database (Suggested tables, important fields, simple explanation)
        db_tables = [
            {
                "name": "users",
                "explanation": "Stores who is registered in the system.",
                "fields": [
                    {"name": "id", "type": "Number (Primary Key)", "desc": "Unique number for each person"},
                    {"name": "name", "type": "Text", "desc": "Full name of the student or teacher"},
                    {"name": "email", "type": "Text", "desc": "Login email address"},
                    {"name": "password_hash", "type": "Secret Text", "desc": "Encrypted password for safety"},
                    {"name": "role", "type": "Text", "desc": "Either student, teacher, or admin"}
                ],
                "relationships": "One user can create multiple project records."
            },
            {
                "name": "items / records",
                "explanation": f"Stores the main records for {title} (e.g. tasks, entries, attendance).",
                "fields": [
                    {"name": "id", "type": "Number (Primary Key)", "desc": "Unique ID of this item"},
                    {"name": "user_id", "type": "Number (Foreign Key)", "desc": "Points to the user who owns this record"},
                    {"name": "title", "type": "Text", "desc": "Main title or name of the record"},
                    {"name": "status", "type": "Text", "desc": "Current state (e.g. Not Started, In Progress, Done)"},
                    {"name": "created_at", "type": "Date/Time", "desc": "When this record was added"}
                ],
                "relationships": "Linked to the users table so only the right person can edit it."
            },
            {
                "name": "activity_logs",
                "explanation": "Keeps a history of important updates for evaluations.",
                "fields": [
                    {"name": "id", "type": "Number (Primary Key)", "desc": "Unique log entry ID"},
                    {"name": "item_id", "type": "Number", "desc": "Which record was updated"},
                    {"name": "notes", "type": "Text", "desc": "What changed or advice given by AI"},
                    {"name": "updated_at", "type": "Date/Time", "desc": "Date and time of change"}
                ],
                "relationships": "Belongs to the main records table."
            }
        ]

        # 6. Development Plan (Step-by-step roadmap with 8 steps)
        dev_plan_steps = [
            {"step": 1, "title": "Plan the project", "desc": "Decide what your project does, who will use it, and list your must-have features.", "status": "Done"},
            {"step": 2, "title": "Create the UI", "desc": "Design simple, friendly web pages with forms, buttons, and summary cards.", "status": "In Progress" if tasks else "Not Started"},
            {"step": 3, "title": "Build the backend", "desc": "Write server routes in Python to accept data from your forms safely.", "status": "In Progress" if any(t.status == 'In Progress' for t in tasks) else "Not Started"},
            {"step": 4, "title": "Create the database", "desc": "Set up database tables so your information is saved cleanly.", "status": "In Progress" if any(t.category == 'Database' and t.status == 'Completed' for t in tasks) else "Not Started"},
            {"step": 5, "title": "Connect everything", "desc": "Link your web buttons to your backend routes and database.", "status": "Not Started"},
            {"step": 6, "title": "Add important features", "desc": "Build the main unique features described in your project proposal.", "status": "Not Started"},
            {"step": 7, "title": "Test the application", "desc": "Try logging in, entering wrong passwords, and clicking every button to make sure it never crashes.", "status": "Not Started"},
            {"step": 8, "title": "Deploy the application", "desc": "Put your working website on a free cloud host so your college guide can view it live.", "status": "Not Started"}
        ]

        # 7. Tasks list (Directly from project tasks)
        tasks_data = []
        for t in tasks:
            tasks_data.append({
                "id": t.id,
                "title": t.title,
                "description": t.description or "Complete this step to advance your project score.",
                "priority": t.priority,
                "status": t.status,
                "category": t.category,
                "phase": t.phase,
                "estimated_hours": t.estimated_hours
            })

        # 8. Testing (Simple test cases)
        test_cases = [
            {
                "test_name": "New User Account Creation",
                "what_to_test": "Register a new student account with valid name, email, and password.",
                "expected_result": "Account is created safely, password is encrypted, and user is redirected to the dashboard.",
                "status": "Ready to Test"
            },
            {
                "test_name": "Wrong Password Defense",
                "what_to_test": "Try logging in using an incorrect password.",
                "expected_result": "App shows a polite error message: 'Invalid email or password' and blocks entry.",
                "status": "Ready to Test"
            },
            {
                "test_name": "Empty Form Field Check",
                "what_to_test": "Try submitting a blank form without entering required title or details.",
                "expected_result": "System stops the form submission and highlights the missing fields in red.",
                "status": "Ready to Test"
            },
            {
                "test_name": "Main Feature Execution",
                "what_to_test": f"Add, view, and update a core item in {title}.",
                "expected_result": "Record appears immediately on the screen and stays visible after refreshing the page.",
                "status": "Ready to Test"
            },
            {
                "test_name": "Mobile Screen Check",
                "what_to_test": "Open the project on a smartphone or shrink your browser window.",
                "expected_result": "Buttons and text fit neatly on the screen without horizontal scrolling.",
                "status": "Ready to Test"
            }
        ]

        # 9. Security (Relevant practical tips for students)
        security_tips = [
            {
                "title": "Secure Login & Password Protection",
                "explanation": "Never save plain text passwords in your database. Always use password hashing like `generate_password_hash()` so nobody can read user passwords.",
                "icon": "fas fa-key text-warning"
            },
            {
                "title": "Input Validation & Clean Data",
                "explanation": "Always verify what users type into forms. Check that email addresses have '@' and remove dangerous script tags before saving.",
                "icon": "fas fa-shield-alt text-primary"
            },
            {
                "title": "Access Control (Who Can See What)",
                "explanation": "Make sure regular students cannot open teacher or admin pages simply by guessing the URL in the address bar.",
                "icon": "fas fa-user-lock text-danger"
            },
            {
                "title": "Database Safety (SQL Injection Prevention)",
                "explanation": "Use an ORM like SQLAlchemy rather than putting user text directly into raw SQL strings. This stops hackers from damaging your database.",
                "icon": "fas fa-database text-success"
            },
            {
                "title": "Safe API Usage & Secret Keys",
                "explanation": "Store API tokens and secret keys in a `.env` file instead of writing them directly inside your public GitHub code.",
                "icon": "fas fa-lock text-info"
            }
        ]

        return {
            "overview": overview_data,
            "what_to_build": what_to_build_data,
            "tools_to_use": tools_list,
            "how_it_works": how_it_works_data,
            "database": db_tables,
            "development_plan": dev_plan_steps,
            "tasks": tasks_data,
            "testing": test_cases,
            "security": security_tips
        }


    def _enrich_plan_response(self, parsed: Dict[str, Any], title: str, domain: str) -> Dict[str, Any]:
        """Ensures both structured phases and flattened core_tasks/optional_tasks exist with requirement_source."""
        phases = parsed.get("phases", [])
        core_tasks = []
        optional_tasks = []

        for phase in phases:
            p_name = phase.get("name", "Phase 1 — Research & Planning")
            p_num = phase.get("phase_number", 1)
            for t in phase.get("tasks", []):
                req_src = t.get("requirement_source", "") or t.get("reason", "")
                task_item = {
                    "task_title": t.get("title") or t.get("task_title", "Milestone Task"),
                    "title": t.get("title") or t.get("task_title", "Milestone Task"),
                    "description": t.get("description", ""),
                    "priority": t.get("priority", "High"),
                    "category": t.get("category", "Backend"),
                    "estimated_difficulty": t.get("difficulty") or t.get("estimated_difficulty", "Medium"),
                    "difficulty": t.get("difficulty") or t.get("estimated_difficulty", "Medium"),
                    "estimated_hours": float(t.get("estimated_hours", 4.0)),
                    "phase": p_name,
                    "phase_number": p_num,
                    "can_parallel": bool(t.get("can_parallel", False)),
                    "dependencies": t.get("dependencies", []),
                    "requirement_source": req_src,
                    "reason": t.get("reason", "")
                }
                # Sync phase task fields
                t["requirement_source"] = req_src
                t["title"] = task_item["title"]
                t["task_title"] = task_item["title"]
                t["phase"] = p_name
                t["phase_number"] = p_num

                if task_item["priority"] == "Optional":
                    optional_tasks.append(task_item)
                else:
                    core_tasks.append(task_item)

        parsed["core_tasks"] = core_tasks
        parsed["optional_tasks"] = optional_tasks
        if "project_summary" not in parsed:
            parsed["project_summary"] = f"A robust {domain} system designed for {title}."
        if "suggested_technologies" not in parsed:
            parsed["suggested_technologies"] = ["Python", "Flask", "React", "PostgreSQL", "Tailwind CSS"]
        if "system_architecture" not in parsed:
            parsed["system_architecture"] = "Three-tier architecture with REST API endpoints, relational database persistence, and a modern responsive dashboard."
        return parsed

    def _generate_rule_based_project_understanding(
        self,
        title: str,
        description: str,
        domain: str = "Web Development",
        technologies_known: str = "",
        team_size: int = 1
    ) -> Dict[str, Any]:
        """
        Rule-based Stage 1 project understanding generator.
        Extracts features from description text, computes confidence score based on detail level,
        and identifies clarification questions if underspecified.
        """
        desc_clean = (description or "").strip()
        words = [w for w in re.split(r"\s+", desc_clean) if w]
        full_text = (title + " " + desc_clean).lower()

        # 1. Determine domain and project type by prioritizing explicit domain
        dom_lower = (domain or "").lower()
        if "machine learning" in dom_lower or "ai" in dom_lower:
            domain = "Machine Learning & AI"
            project_type = "Machine Learning Pipeline"
            default_tech = ["Python", "PyTorch / Scikit-Learn", "Pandas / NumPy", "FastAPI / Flask"]
        elif "iot" in dom_lower or "internet of things" in dom_lower:
            domain = "Internet of Things (IoT)"
            project_type = "Internet of Things (IoT)"
            default_tech = ["C++ / Arduino", "ESP32 / Raspberry Pi", "MQTT", "Python / Flask", "SQLite"]
        elif "data science" in dom_lower or "analytics" in dom_lower:
            domain = "Data Science"
            project_type = "Data Science & Analytics"
            default_tech = ["Python", "Pandas", "Matplotlib / Seaborn", "Streamlit / Flask", "PostgreSQL"]
        elif "mobile" in dom_lower:
            domain = "Mobile Applications"
            project_type = "Mobile Application"
            default_tech = ["Flutter / React Native", "Node.js / Express", "Firebase / SQLite"]
        elif any(w in full_text for w in ["machine learning", "deep learning", "neural network", "nlp", "computer vision", "predictive model", "train model"]):
            domain = "Machine Learning & AI"
            project_type = "Machine Learning Pipeline"
            default_tech = ["Python", "PyTorch / Scikit-Learn", "Pandas / NumPy", "FastAPI / Flask"]
        elif any(w in full_text for w in ["iot", "arduino", "esp32", "hardware prototype", "raspberry pi", "mqtt", "microcontroller"]):
            domain = "Internet of Things (IoT)"
            project_type = "Internet of Things (IoT)"
            default_tech = ["C++ / Arduino", "ESP32 / Raspberry Pi", "MQTT", "Python / Flask", "SQLite"]
        elif any(w in full_text for w in ["analytics", "data science", "dashboard", "visualization", "dataset analysis"]):
            domain = "Data Science"
            project_type = "Data Science & Analytics"
            default_tech = ["Python", "Pandas", "Matplotlib / Seaborn", "Streamlit / Flask", "PostgreSQL"]
        elif any(w in full_text for w in ["mobile app", "android app", "ios app", "flutter", "react native"]):
            domain = "Mobile Applications"
            project_type = "Mobile Application"
            default_tech = ["Flutter / React Native", "Node.js / Express", "Firebase / SQLite"]
        else:
            domain = domain or "Web Development"
            project_type = "Web Application"
            default_tech = ["Python / Flask", "HTML5 / JavaScript", "SQLite / PostgreSQL", "Bootstrap 5"]

        # Merge known tech
        known_list = [k.strip() for k in technologies_known.split(",") if k.strip()]
        for k in known_list:
            if k not in default_tech:
                default_tech.insert(0, k)

        # 2. Extract features from description
        raw_chunks = re.split(r"[\n\r;•\.]+|\band\b", desc_clean)
        features = []
        for chunk in raw_chunks:
            c = chunk.strip().strip("- ")
            if len(c) > 10 and not any(c.lower().startswith(x) for x in ["a web app", "a mobile app", "this project", "it is designed", "project description"]):
                features.append(c.capitalize())

        if not features:
            features = [
                f"Core functional workflow for {title}",
                f"Interactive user interface and reporting views for {title}",
                f"Data persistence, verification, and export capabilities"
            ]

        # 3. Detect target users
        expected_users = []
        if "student" in full_text: expected_users.append("Students")
        if "teacher" in full_text or "faculty" in full_text: expected_users.append("Faculty / Instructors")
        if "admin" in full_text: expected_users.append("System Administrators")
        if "doctor" in full_text or "patient" in full_text: expected_users.append("Medical Staff / Patients")
        if not expected_users:
            expected_users = ["Primary Application Users", "System Administrator"]

        # 4. Confidence & Clarification scoring
        is_brief = len(desc_clean) < 45 or len(words) < 7
        if is_brief:
            confidence = 60.0
            clarification_required = True
            questions = [
                f"What are the specific features and user capabilities for '{title}'?",
                f"Who are the target user roles (e.g. students, teachers, administrators)?",
                f"What platform (Web application, mobile app, data science pipeline, or IoT hardware) are you building?"
            ]
        else:
            confidence = 92.0
            clarification_required = False
            questions = []

        return {
            "title": title,
            "description": description,
            "domain": domain,
            "project_type": project_type,
            "project_summary": f"A dedicated {project_type.lower()} in the {domain} domain implementing {title.lower()}, focused on {features[0].lower() if features else 'core functionality'}.",
            "core_objective": f"Deliver a reliable, project-specific {domain} solution for {title}.",
            "required_features": features[:6],
            "optional_features": [f"Advanced export and analytics for {title}"],
            "expected_users": expected_users,
            "technologies": default_tech[:5],
            "required_data": [f"{title} input records and schema fixtures"],
            "required_integrations": ["Local database engine", "RESTful API endpoints"],
            "technology_difficulty": "Medium",
            "confidence_score": confidence,
            "clarification_required": clarification_required,
            "clarification_questions": questions
        }

    def _generate_rule_based_tasks_from_requirements(
        self,
        understanding: Dict[str, Any],
        custom_instructions: str = "",
        team_size: int = 1
    ) -> Dict[str, Any]:
        """
        Dynamically constructs project-specific phases and concrete tasks
        mapped directly to the validated requirements.
        """
        title = understanding.get("title", "Project")
        domain = understanding.get("domain", "Web Development")
        project_type = understanding.get("project_type", "Web Application")
        features = understanding.get("required_features", [])
        tech = understanding.get("technologies", ["Python", "Flask", "SQLite"])
        summary = understanding.get("project_summary", "")

        dom_lower = domain.lower()
        is_ml = "machine learning" in dom_lower or "ai" in dom_lower or project_type == "Machine Learning Pipeline"
        is_iot = not is_ml and (project_type in ["Internet of Things (IoT)", "Hardware Prototype"] or "iot" in dom_lower or "hardware" in dom_lower)
        is_data = not is_ml and not is_iot and ("data science" in dom_lower or project_type == "Data Science & Analytics")

        phases = []

        if is_iot:
            # IoT Phases
            phase_names = [
                "Phase 1 — Architecture & Component Selection",
                "Phase 2 — Circuit Design & Schematic",
                "Phase 3 — Firmware & Sensor Interfacing",
                "Phase 4 — Cloud & Telemetry Integration",
                "Phase 5 — Hardware Testing & Calibration",
                "Phase 6 — Project Documentation & Defense"
            ]
            phases.append({
                "phase_number": 1,
                "name": phase_names[0],
                "tasks": [
                    {
                        "title": f"Specify sensor pinout, power budget & hardware architecture for {title}",
                        "description": f"Calculate power consumption, select microcontroller ({tech[0] if tech else 'ESP32'}), and map sensor GPIO connections.",
                        "category": "Hardware", "priority": "Critical", "difficulty": "Medium", "estimated_hours": 4.0, "can_parallel": True,
                        "dependencies": [], "requirement_source": "Hardware architecture & power budgeting",
                        "reason": "Foundational hardware specification preventing electrical overload and pin conflicts."
                    },
                    {
                        "title": f"Procure & benchmark sensor modules for {title}",
                        "description": "Verify sensor operating voltages, test communication protocols (I2C/SPI), and document baseline calibration curves.",
                        "category": "Hardware", "priority": "High", "difficulty": "Easy", "estimated_hours": 3.0, "can_parallel": True,
                        "dependencies": [f"Specify sensor pinout, power budget & hardware architecture for {title}"],
                        "requirement_source": features[0] if features else "Sensor hardware selection",
                        "reason": "Ensures sensor components operate within required measurement thresholds."
                    }
                ]
            })
            phases.append({
                "phase_number": 2,
                "name": phase_names[1],
                "tasks": [
                    {
                        "title": f"Design circuit schematic & wiring diagram for {title}",
                        "description": "Create detailed wiring schematic showing pull-up resistors, decoupling capacitors, and power regulation.",
                        "category": "Hardware", "priority": "Critical", "difficulty": "Medium", "estimated_hours": 4.0, "can_parallel": False,
                        "dependencies": [f"Specify sensor pinout, power budget & hardware architecture for {title}"],
                        "requirement_source": "Circuit design & power safety",
                        "reason": "Prevents wiring shorts during live hardware evaluation."
                    }
                ]
            })
            phases.append({
                "phase_number": 3,
                "name": phase_names[2],
                "tasks": [
                    {
                        "title": f"Implement microcontroller firmware for {features[0] if features else 'sensor data reading'}",
                        "description": "Write embedded driver to sample analog/digital values at regular polling intervals with error timeouts.",
                        "category": "Hardware", "priority": "Critical", "difficulty": "Medium", "estimated_hours": 6.0, "can_parallel": False,
                        "dependencies": [f"Design circuit schematic & wiring diagram for {title}"],
                        "requirement_source": features[0] if features else "Microcontroller firmware",
                        "reason": "Core firmware logic for physical data acquisition."
                    }
                ]
            })
            phases.append({
                "phase_number": 4,
                "name": phase_names[3],
                "tasks": [
                    {
                        "title": f"Implement MQTT / HTTP telemetry publishing for {title}",
                        "description": "Configure WiFi connection, secure MQTT payload publishing, and cloud telemetry logging.",
                        "category": "Backend", "priority": "High", "difficulty": "Medium", "estimated_hours": 5.0, "can_parallel": False,
                        "dependencies": [f"Implement microcontroller firmware for {features[0] if features else 'sensor data reading'}"],
                        "requirement_source": features[1] if len(features) > 1 else "Telemetry cloud gateway",
                        "reason": "Enables remote real-time monitoring of device telemetry."
                    }
                ]
            })
            phases.append({
                "phase_number": 5,
                "name": phase_names[4],
                "tasks": [
                    {
                        "title": f"Perform sensor calibration, noise filtering & hardware stress tests",
                        "description": "Test readings against reference standards, implement moving-average smoothing, and test network drop reconnection.",
                        "category": "Testing", "priority": "Critical", "difficulty": "Medium", "estimated_hours": 4.0, "can_parallel": True,
                        "dependencies": [f"Implement MQTT / HTTP telemetry publishing for {title}"],
                        "requirement_source": "Hardware reliability & measurement accuracy",
                        "reason": "Eliminates sensor jitter and false alerts during project demonstration."
                    }
                ]
            })
            phases.append({
                "phase_number": 6,
                "name": phase_names[5],
                "tasks": [
                    {
                        "title": f"Prepare circuit diagrams, bill of materials (BOM) & final thesis report",
                        "description": "Compile complete project report with schematic diagrams, calibration curves, and viva defense slides.",
                        "category": "Documentation", "priority": "Critical", "difficulty": "Easy", "estimated_hours": 6.0, "can_parallel": True,
                        "dependencies": [],
                        "requirement_source": "Academic capstone deliverable",
                        "reason": "Required for external viva evaluation and grading."
                    }
                ]
            })

        elif is_ml:
            # Machine Learning Phases
            phase_names = [
                "Phase 1 — Problem Definition & Data Sourcing",
                "Phase 2 — Data Preprocessing & Exploratory Analysis",
                "Phase 3 — Feature Engineering & Preprocessing Pipeline",
                "Phase 4 — Model Architecture & Training",
                "Phase 5 — Model Evaluation & Metric Validation",
                "Phase 6 — Model Serving & Capstone Report"
            ]
            phases.append({
                "phase_number": 1,
                "name": phase_names[0],
                "tasks": [
                    {
                        "title": f"Acquire, inspect & validate benchmark dataset for {title}",
                        "description": "Source primary dataset, verify row count, inspect class distributions, and document licensing.",
                        "category": "Research", "priority": "Critical", "difficulty": "Easy", "estimated_hours": 4.0, "can_parallel": True,
                        "dependencies": [], "requirement_source": features[0] if features else "Dataset acquisition",
                        "reason": "Provides clean ground-truth training and evaluation data."
                    }
                ]
            })
            phases.append({
                "phase_number": 2,
                "name": phase_names[1],
                "tasks": [
                    {
                        "title": f"Perform exploratory data analysis (EDA) & missing value imputation for {title}",
                        "description": "Analyze feature correlations, generate distribution histograms, and handle missing/outlier records.",
                        "category": "Machine Learning", "priority": "High", "difficulty": "Medium", "estimated_hours": 5.0, "can_parallel": False,
                        "dependencies": [f"Acquire, inspect & validate benchmark dataset for {title}"],
                        "requirement_source": "Data quality & distribution inspection",
                        "reason": "Prevents training distortions caused by skewed or dirty data."
                    }
                ]
            })
            phases.append({
                "phase_number": 3,
                "name": phase_names[2],
                "tasks": [
                    {
                        "title": f"Construct feature transformation & scaling pipeline for {features[0] if features else 'model inputs'}",
                        "description": "Implement standard scaling, one-hot encoding, and train/validation/test stratified splitting.",
                        "category": "Machine Learning", "priority": "Critical", "difficulty": "Medium", "estimated_hours": 4.0, "can_parallel": False,
                        "dependencies": [f"Perform exploratory data analysis (EDA) & missing value imputation for {title}"],
                        "requirement_source": features[0] if features else "Feature engineering",
                        "reason": "Ensures reproducible numerical input matrices for model training."
                    }
                ]
            })
            phases.append({
                "phase_number": 4,
                "name": phase_names[3],
                "tasks": [
                    {
                        "title": f"Train baseline & optimized models for {title}",
                        "description": "Train candidate ML models, perform hyperparameter tuning using cross-validation, and log loss curves.",
                        "category": "Machine Learning", "priority": "Critical", "difficulty": "Hard", "estimated_hours": 8.0, "can_parallel": False,
                        "dependencies": [f"Construct feature transformation & scaling pipeline for {features[0] if features else 'model inputs'}"],
                        "requirement_source": features[1] if len(features) > 1 else features[0] if features else "Model training",
                        "reason": "Central computational deliverable for machine learning capstone."
                    }
                ]
            })
            phases.append({
                "phase_number": 5,
                "name": phase_names[4],
                "tasks": [
                    {
                        "title": f"Evaluate model performance (Confusion Matrix, Precision/Recall, ROC-AUC)",
                        "description": "Benchmark final model against test split, plot confusion matrix, and analyze prediction error cases.",
                        "category": "Testing", "priority": "Critical", "difficulty": "Medium", "estimated_hours": 4.0, "can_parallel": True,
                        "dependencies": [f"Train baseline & optimized models for {title}"],
                        "requirement_source": "Model validation & evaluation rigor",
                        "reason": "Provides quantitative evidence of model effectiveness for examiners."
                    }
                ]
            })
            phases.append({
                "phase_number": 6,
                "name": phase_names[5],
                "tasks": [
                    {
                        "title": f"Build inference REST API & compile academic project report for {title}",
                        "description": "Wrap model in FastAPI/Flask inference endpoint and write comprehensive academic thesis report.",
                        "category": "Documentation", "priority": "High", "difficulty": "Medium", "estimated_hours": 6.0, "can_parallel": True,
                        "dependencies": [f"Evaluate model performance (Confusion Matrix, Precision/Recall, ROC-AUC)"],
                        "requirement_source": "Academic capstone deliverable & deployment",
                        "reason": "Enables interactive model demonstration during viva panel."
                    }
                ]
            })

        elif is_data:
            # Data Science Phases
            phase_names = [
                "Phase 1 — Requirements & Data Sourcing",
                "Phase 2 — Data Cleansing & Validation",
                "Phase 3 — Exploratory Data Analysis & Correlation",
                "Phase 4 — Analytical Modeling & Visual Dashboards",
                "Phase 5 — Metric Validation & Sensitivity Analysis",
                "Phase 6 — Insights Report & Presentation"
            ]
            phases.append({
                "phase_number": 1,
                "name": phase_names[0],
                "tasks": [
                    {
                        "title": f"Define analytic objectives & source primary dataset for {title}",
                        "description": "Establish key performance indicators (KPIs), acquire raw data files, and verify schema integrity.",
                        "category": "Research", "priority": "Critical", "difficulty": "Easy", "estimated_hours": 3.0, "can_parallel": True,
                        "dependencies": [], "requirement_source": features[0] if features else "Data acquisition",
                        "reason": "Establishes data baseline for analysis."
                    }
                ]
            })
            phases.append({
                "phase_number": 2,
                "name": phase_names[1],
                "tasks": [
                    {
                        "title": f"Build automated data cleaning & deduplication scripts for {title}",
                        "description": "Write pandas scripts to cleanse anomalies, standardize timestamps, and handle null records.",
                        "category": "Backend", "priority": "High", "difficulty": "Medium", "estimated_hours": 4.0, "can_parallel": False,
                        "dependencies": [f"Define analytic objectives & source primary dataset for {title}"],
                        "requirement_source": "Data quality assurance",
                        "reason": "Guarantees clean data input for dashboard visualization."
                    }
                ]
            })
            phases.append({
                "phase_number": 3,
                "name": phase_names[2],
                "tasks": [
                    {
                        "title": f"Conduct statistical exploratory data analysis & trend discovery",
                        "description": "Generate summary statistics, calculate correlation coefficients, and identify key drivers.",
                        "category": "Research", "priority": "High", "difficulty": "Medium", "estimated_hours": 5.0, "can_parallel": False,
                        "dependencies": [f"Build automated data cleaning & deduplication scripts for {title}"],
                        "requirement_source": features[1] if len(features) > 1 else features[0] if features else "Trend discovery",
                        "reason": "Discovers analytical insights to answer core project questions."
                    }
                ]
            })
            phases.append({
                "phase_number": 4,
                "name": phase_names[3],
                "tasks": [
                    {
                        "title": f"Build interactive analytics dashboard & visualization charts for {title}",
                        "description": "Create responsive dashboard with filterable charts, aggregate summaries, and drill-down views.",
                        "category": "Frontend", "priority": "Critical", "difficulty": "Medium", "estimated_hours": 6.0, "can_parallel": False,
                        "dependencies": [f"Conduct statistical exploratory data analysis & trend discovery"],
                        "requirement_source": features[0] if features else "Interactive dashboard",
                        "reason": "Primary user interface demonstrating analytical findings."
                    }
                ]
            })
            phases.append({
                "phase_number": 5,
                "name": phase_names[4],
                "tasks": [
                    {
                        "title": f"Validate metric calculations & perform sensitivity analysis",
                        "description": "Run automated test fixtures to verify dashboard formulas, aggregations, and edge cases.",
                        "category": "Testing", "priority": "High", "difficulty": "Easy", "estimated_hours": 3.0, "can_parallel": True,
                        "dependencies": [f"Build interactive analytics dashboard & visualization charts for {title}"],
                        "requirement_source": "Metric validation",
                        "reason": "Ensures calculations displayed to faculty evaluators are mathematically sound."
                    }
                ]
            })
            phases.append({
                "phase_number": 6,
                "name": phase_names[5],
                "tasks": [
                    {
                        "title": f"Compile comprehensive data insights report & executive slide deck",
                        "description": "Draft findings chapter, document methodology, export high-res visual plots, and prepare defense deck.",
                        "category": "Documentation", "priority": "Critical", "difficulty": "Easy", "estimated_hours": 5.0, "can_parallel": True,
                        "dependencies": [], "requirement_source": "Academic report deliverable",
                        "reason": "Essential academic capstone submission."
                    }
                ]
            })

        else:
            # Web / Software Application
            phase_names = [
                "Phase 1 — Research & Requirement Specification",
                "Phase 2 — UI/UX Wireframing & Design",
                "Phase 3 — Core Feature & API Development",
                "Phase 4 — Database Persistence & Schema Design",
                "Phase 5 — Integration Testing & Quality Assurance",
                "Phase 6 — Deployment & Academic Documentation"
            ]
            phases.append({
                "phase_number": 1,
                "name": phase_names[0],
                "tasks": [
                    {
                        "title": f"Analyze functional requirements & user workflows for {title}",
                        "description": f"Document user roles, input/output data flows, and specify API contracts for {', '.join(features[:2]) if features else 'core modules'}.",
                        "category": "Research", "priority": "High", "difficulty": "Easy", "estimated_hours": 3.0, "can_parallel": True,
                        "dependencies": [], "requirement_source": features[0] if features else "Requirements analysis",
                        "reason": "Prevents feature creep and defines development scope."
                    }
                ]
            })
            phases.append({
                "phase_number": 2,
                "name": phase_names[1],
                "tasks": [
                    {
                        "title": f"Design user interface layouts & views for {features[0] if features else title}",
                        "description": "Design clean, responsive web views with intuitive forms, feedback states, and modern layout.",
                        "category": "Frontend", "priority": "High", "difficulty": "Medium", "estimated_hours": 4.0, "can_parallel": True,
                        "dependencies": [f"Analyze functional requirements & user workflows for {title}"],
                        "requirement_source": features[0] if features else "User interface design",
                        "reason": "Primary user interaction surface."
                    }
                ]
            })

            # Feature-driven tasks in Phase 3
            dev_tasks = []
            for i, f in enumerate(features[:3]):
                dev_tasks.append({
                    "title": f"Implement backend controllers & business logic for {f}",
                    "description": f"Write server-side endpoints, validation logic, and state handling specifically for {f}.",
                    "category": "Backend", "priority": "Critical", "difficulty": "Medium", "estimated_hours": 5.0, "can_parallel": i > 0,
                    "dependencies": [f"Analyze functional requirements & user workflows for {title}"],
                    "requirement_source": f,
                    "reason": f"Fulfills core requirement: {f}"
                })
            if not dev_tasks:
                dev_tasks.append({
                    "title": f"Implement core application controllers and business logic for {title}",
                    "description": "Develop server-side routing, request validation, and processing logic.",
                    "category": "Backend", "priority": "Critical", "difficulty": "Medium", "estimated_hours": 6.0, "can_parallel": False,
                    "dependencies": [f"Analyze functional requirements & user workflows for {title}"],
                    "requirement_source": "Core application logic",
                    "reason": "Central functional deliverable of the project."
                })

            phases.append({
                "phase_number": 3,
                "name": phase_names[2],
                "tasks": dev_tasks
            })

            phases.append({
                "phase_number": 4,
                "name": phase_names[3],
                "tasks": [
                    {
                        "title": f"Design relational schema & database tables for {title}",
                        "description": f"Create normalized database models, define primary/foreign keys, and configure indexes for fast querying.",
                        "category": "Database", "priority": "Critical", "difficulty": "Medium", "estimated_hours": 4.0, "can_parallel": False,
                        "dependencies": [f"Analyze functional requirements & user workflows for {title}"],
                        "requirement_source": "Data persistence and relational integrity",
                        "reason": "Provides reliable persistent storage for all application entities."
                    }
                ]
            })

            phases.append({
                "phase_number": 5,
                "name": phase_names[4],
                "tasks": [
                    {
                        "title": f"Implement automated endpoint tests & edge-case validation for {title}",
                        "description": f"Write test cases for input sanitization, error responses, and verify successful operations for {features[0] if features else 'core features'}.",
                        "category": "Testing", "priority": "Critical", "difficulty": "Medium", "estimated_hours": 4.0, "can_parallel": True,
                        "dependencies": [dev_tasks[0]["title"]],
                        "requirement_source": "Quality assurance and defect prevention",
                        "reason": "Guarantees system stability during evaluation."
                    }
                ]
            })

            phases.append({
                "phase_number": 6,
                "name": phase_names[5],
                "tasks": [
                    {
                        "title": f"Write academic capstone project report & prepare viva defense slides",
                        "description": f"Document system architecture, database schema, implementation details, and create viva demo slides.",
                        "category": "Documentation", "priority": "Critical", "difficulty": "Easy", "estimated_hours": 6.0, "can_parallel": True,
                        "dependencies": [], "requirement_source": "Academic capstone deliverable",
                        "reason": "Primary graded component for academic degree evaluation."
                    }
                ]
            })

        # Generate contextual AI tools matching the domain
        ai_tools = [
            {
                "stage": phases[0]["name"],
                "tool_name": "ChatGPT / Perplexity AI",
                "purpose": f"Literature survey, requirement extraction, and state-of-the-art comparison for {title}",
                "ready_to_use_prompt": f"Act as an academic advisor. Analyze my project '{title}' in the {domain} domain. Generate a comparative matrix of existing approaches, key technical risks, and architectural best practices."
            },
            {
                "stage": phases[2]["name"],
                "tool_name": "GitHub Copilot / Cursor AI",
                "purpose": f"Scaffolding modules, boilerplate code, and testing for {features[0] if features else title}",
                "ready_to_use_prompt": f"Generate clean, modular code for '{title}' implementing {features[0] if features else 'core features'} using {tech[0] if tech else 'Python'} with error handling and docstrings."
            },
            {
                "stage": phases[4]["name"],
                "tool_name": "Pytest / Postman",
                "purpose": f"Automated test suite generation and edge-case validation",
                "ready_to_use_prompt": f"Generate automated test cases for '{title}' covering valid inputs, boundary conditions, and invalid inputs."
            },
            {
                "stage": phases[5]["name"],
                "tool_name": "LaTeX / Overleaf & Render",
                "purpose": "Academic report drafting and cloud deployment configuration",
                "ready_to_use_prompt": f"Draft the system implementation and evaluation chapter for my academic project report titled '{title}'."
            }
        ]

        result = {
            "project_type": project_type,
            "domain": domain,
            "project_summary": summary or f"A dedicated {domain} project designed to implement {title}.",
            "main_objective": understanding.get("core_objective", f"Deliver an end-to-end working system for {title}."),
            "technology_difficulty": understanding.get("technology_difficulty", "Medium"),
            "suggested_technologies": tech,
            "system_architecture": f"Modern modular architecture tailored to {project_type}: Layered services with {tech[0] if tech else 'core engine'}, robust persistence, and automated validation.",
            "phases": phases,
            "ai_tools": ai_tools,
            "parallel_tasks_advice": "Team members can work on UI/frontend wireframing and database schema design concurrently once Phase 1 requirements are confirmed.",
            "prioritized_tasks": [
                phases[0]["tasks"][0]["title"],
                phases[2]["tasks"][0]["title"]
            ]
        }
        return result

    def _generate_rule_based_analysis(
        self,
        title: str,
        description: str,
        domain: str = "Web Development",
        technologies_known: str = "",
        team_size: int = 1
    ) -> Dict[str, Any]:
        """
        Backward-compatible rule-based generator that uses Stage 1 understanding
        and Stage 2 task generation.
        """
        understanding = self._generate_rule_based_project_understanding(
            title=title,
            description=description,
            domain=domain,
            technologies_known=technologies_known,
            team_size=team_size
        )
        plan = self._generate_rule_based_tasks_from_requirements(
            understanding=understanding,
            custom_instructions="",
            team_size=team_size
        )
        plan["project_analysis"] = understanding
        return self._enrich_plan_response(plan, title, domain)

    def _call_gemini_api(self, prompt: str) -> str:
        """Invokes Google Gemini API directly using REST protocol with multi-model fallback."""
        import urllib.request
        import json

        models = [
            self.gemini_model or "gemini-3.5-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-flash-lite-latest"
        ]
        models_dedup = []
        for m in models:
            if m and m not in models_dedup:
                models_dedup.append(m)

        for m in models_dedup:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.gemini_key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json"
                }
            }
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    candidates = body.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
            except Exception as e:
                logger.warning(f"AIService Gemini model {m} failed: {e}")
                continue
        return ""

    def _call_llm(self, prompt: str) -> str:
        """Helper to invoke OpenAI-compatible endpoint."""
        import urllib.request
        import json

        base_url = self.base_url or "https://api.openai.com/v1"
        url = f"{base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are Projexa's expert AI Academic Project Mentor. Output only valid JSON when requested."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }

        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            res_body = json.loads(response.read().decode("utf-8"))
            return res_body["choices"][0]["message"]["content"]

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Safely parses JSON even if wrapped in markdown codeblocks."""
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end+1])
                except Exception:
                    pass
        return {}


# Global Singleton Instance
_ai_service_instance = None

def get_ai_service() -> AIService:
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance
