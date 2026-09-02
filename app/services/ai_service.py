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
from typing import Dict, List, Any


class AIService:
    def __init__(self):
        self.api_key = os.environ.get("AI_API_KEY", "")
        self.model = os.environ.get("AI_MODEL", "gpt-4o-mini")
        self.base_url = os.environ.get("AI_BASE_URL", "")

    def analyze_project_and_generate_tasks(self, title: str, description: str) -> Dict[str, Any]:
        """
        Analyzes the project title and description to produce a comprehensive
        structured JSON plan with core and optional development tasks.
        """
        prompt = f"""You are ProjectGuard's AI Academic Project Mentor.
Analyze the following student project and break it down into a structured, realistic academic development plan.

PROJECT TITLE: {title}
PROJECT DESCRIPTION: {description}

Return ONLY valid JSON matching this schema:
{{
  "project_summary": "A concise 2-sentence summary of the system architecture and purpose.",
  "main_objective": "The primary problem this project solves.",
  "project_type": "Capstone / Major Project / Mini-Project",
  "domain": "Web Development / Machine Learning & AI / Mobile Applications / IoT / Cloud / Blockchain / Cybersecurity",
  "technology_difficulty": "Easy / Medium / Hard",
  "suggested_technologies": ["Tech1", "Tech2", "Tech3"],
  "suggested_modules": ["Module 1", "Module 2", "Module 3"],
  "core_tasks": [
    {{
      "task_title": "Database Schema Design",
      "description": "Design relational tables for entities and relationships.",
      "priority": "Critical / High / Medium",
      "category": "Database / Backend / Frontend / AI / Testing / Documentation / Deployment",
      "estimated_difficulty": "Medium",
      "dependencies": [],
      "reason": "Foundational requirement for data persistence."
    }}
  ],
  "optional_tasks": [
    {{
      "task_title": "Dark Mode Toggle & UI Polish",
      "description": "Add user theme toggle.",
      "priority": "Optional",
      "category": "UI/UX",
      "estimated_difficulty": "Easy",
      "dependencies": [],
      "reason": "Enhances UX but not required for minimal viable academic demo."
    }}
  ],
  "potential_missing_tasks": ["API Rate Limiting", "Exporting Attendance CSV", "Unit Testing Core Handlers"],
  "risks": ["Voice recognition noise in classroom environments", "Database latency during peak check-in"],
  "questions_for_student": ["Will you use local offline speech recognition or cloud APIs like Whisper/Google Speech?"]
}}
"""
        # Try external LLM if API key is provided
        if self.api_key:
            try:
                response_text = self._call_llm(prompt)
                parsed = self._extract_json(response_text)
                if parsed and "core_tasks" in parsed and len(parsed["core_tasks"]) > 0:
                    return parsed
            except Exception as e:
                print(f"[-] LLM API call error: {e}. Falling back to internal intelligent task generator.")

        # Fallback intelligent domain-aware generator
        return self._generate_rule_based_analysis(title, description)

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

        prompt = f"""You are ProjectGuard's intelligent AI Project Mentor.
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

    def _generate_rule_based_analysis(self, title: str, description: str) -> Dict[str, Any]:
        """
        Intelligent rule-based generator creating a tailored academic project plan
        when external LLM APIs are offline.
        """
        desc_lower = (description + " " + title).lower()

        # Domain classification
        if any(w in desc_lower for w in ["ai", "machine learning", "neural", "deep learning", "nlp", "vision", "dataset", "predict", "classify"]):
            domain = "Machine Learning & AI"
            difficulty = "Hard"
        elif any(w in desc_lower for w in ["iot", "arduino", "esp32", "sensor", "hardware", "raspberry", "mqtt"]):
            domain = "Internet of Things (IoT)"
            difficulty = "Hard"
        elif any(w in desc_lower for w in ["blockchain", "solidity", "ethereum", "web3", "smart contract", "crypto"]):
            domain = "Blockchain"
            difficulty = "Hard"
        elif any(w in desc_lower for w in ["mobile", "android", "ios", "flutter", "react native"]):
            domain = "Mobile Applications"
            difficulty = "Medium"
        else:
            domain = "Web Development"
            difficulty = "Medium"

        summary = f"A {domain.lower()} system designed to {title.lower()}, integrating modern client-server architecture, database persistence, and robust authentication."
        objective = f"Deliver a reliable, fully functional {domain} solution fulfilling academic project requirements."

        core_tasks = [
            {
                "task_title": "System Architecture & Database Schema Design",
                "description": "Design relational/NoSQL schemas, entity relationship diagrams (ERD), and API route contracts.",
                "priority": "Critical",
                "category": "Database",
                "estimated_difficulty": "Medium",
                "dependencies": [],
                "reason": "Foundational requirement before coding application logic."
            },
            {
                "task_title": "User Authentication & Role-Based Access Control",
                "description": "Implement secure password hashing, session tokens, and student/faculty permissions.",
                "priority": "High",
                "category": "Backend",
                "estimated_difficulty": "Medium",
                "dependencies": ["System Architecture & Database Schema Design"],
                "reason": "Protects user data and enforces role separation."
            },
            {
                "task_title": f"Core {title} Feature Implementation",
                "description": f"Develop primary business logic and core workflows described in project scope.",
                "priority": "Critical",
                "category": "Backend" if domain != "Machine Learning & AI" else "Machine Learning",
                "estimated_difficulty": "Hard" if difficulty == "Hard" else "Medium",
                "dependencies": ["User Authentication & Role-Based Access Control"],
                "reason": "The central deliverable of the project."
            },
            {
                "task_title": "Responsive User Interface & Dashboard",
                "description": "Build interactive, accessible client-side UI with status badges and forms.",
                "priority": "High",
                "category": "Frontend",
                "estimated_difficulty": "Medium",
                "dependencies": [f"Core {title} Feature Implementation"],
                "reason": "Required for student/faculty interaction and evaluation demos."
            },
            {
                "task_title": "REST API Integration & Middleware",
                "description": "Connect frontend components with backend API endpoints and data models.",
                "priority": "High",
                "category": "API",
                "estimated_difficulty": "Medium",
                "dependencies": ["Responsive User Interface & Dashboard"],
                "reason": "Enables dynamic asynchronous data exchange."
            },
            {
                "task_title": "Automated Unit & Integration Testing",
                "description": "Write automated test cases verifying core business logic and API responses.",
                "priority": "High",
                "category": "Testing",
                "estimated_difficulty": "Medium",
                "dependencies": ["REST API Integration & Middleware"],
                "reason": "Prevents regressions and verifies system reliability."
            },
            {
                "task_title": "Academic Project Documentation & Thesis Report",
                "description": "Draft comprehensive documentation including methodology, system design, and results.",
                "priority": "High",
                "category": "Documentation",
                "estimated_difficulty": "Medium",
                "dependencies": [],
                "reason": "Required for final capstone submission and grading."
            },
            {
                "task_title": "Final Viva Presentation Slides & Live Demo Setup",
                "description": "Prepare slide deck, demo datasets, and backup walkthrough video for defense.",
                "priority": "Medium",
                "category": "Presentation",
                "estimated_difficulty": "Easy",
                "dependencies": ["Academic Project Documentation & Thesis Report"],
                "reason": "Prepares team for faculty defense examination."
            }
        ]

        # Domain specific additions
        if domain == "Machine Learning & AI":
            core_tasks.insert(2, {
                "task_title": "Dataset Curation, Preprocessing & Feature Engineering",
                "description": "Collect, clean, normalize, and split dataset into stratified train/test partitions.",
                "priority": "Critical",
                "category": "Machine Learning",
                "estimated_difficulty": "Medium",
                "dependencies": [],
                "reason": "Model quality depends directly on clean training data."
            })
            core_tasks.insert(4, {
                "task_title": "Model Training, Hyperparameter Tuning & Evaluation",
                "description": "Train candidate ML models and evaluate Accuracy, Precision, Recall, and ROC-AUC.",
                "priority": "Critical",
                "category": "Machine Learning",
                "estimated_difficulty": "Hard",
                "dependencies": ["Dataset Curation, Preprocessing & Feature Engineering"],
                "reason": "Core AI model selection and benchmarking."
            })

        optional_tasks = [
            {
                "task_title": "Dark Mode & UI Polish",
                "description": "Add optional theme toggle and transition animations.",
                "priority": "Optional",
                "category": "UI/UX",
                "estimated_difficulty": "Easy",
                "dependencies": [],
                "reason": "Nice-to-have visual enhancement; not essential for viva demo."
            },
            {
                "task_title": "CSV / PDF Data Export Utility",
                "description": "Allow users to download reports in PDF or CSV formats.",
                "priority": "Optional",
                "category": "Backend",
                "estimated_difficulty": "Easy",
                "dependencies": [],
                "reason": "Helpful utility feature that can be added if time permits."
            }
        ]

        return {
            "project_summary": summary,
            "main_objective": objective,
            "project_type": "Capstone Project",
            "domain": domain,
            "technology_difficulty": difficulty,
            "suggested_technologies": ["Python", "Flask", "React", "PostgreSQL", "Tailwind CSS"],
            "suggested_modules": ["Authentication Module", "Core Processing Engine", "Reporting & Analytics", "Dashboard UI"],
            "core_tasks": core_tasks,
            "optional_tasks": optional_tasks,
            "potential_missing_tasks": ["API Rate Limiting", "Cross-Browser Compatibility Testing", "Database Backup Script"],
            "risks": ["Underestimating testing duration near the deadline", "Unresolved software bugs affecting live viva demo"],
            "questions_for_student": [
                "Do you plan to host the application online (e.g. Render/Vercel) or demonstrate on a local server?",
                "Have you gathered or generated the required sample data for testing?"
            ]
        }

    def _call_llm(self, prompt: str) -> str:
        """Helper to invoke configured LLM API."""
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
                {"role": "system", "content": "You are ProjectGuard's expert AI Academic Project Mentor. Output only valid JSON when requested."},
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
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if match:
                try:
                    return json.loads(match.group(1))
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
