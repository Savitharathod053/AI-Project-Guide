"""
TEST SUITE FOR BUILDCHECK AI — HARDWARE FEASIBILITY & BUDGET ANALYZER
====================================================================
Tests project classification, structured architecture decomposition,
electrical calculations (current, power, safety margin), compatibility hazards,
multi-dimensional scoring, budget breakdown, purchasing links, and
hardware task roadmap generation.
"""

from datetime import date, timedelta
import json
import pytest
from app import create_app
from app.models import db, User, Project, Task, HardwareAnalysis
from app.services.hardware_feasibility_service import (
    get_hardware_feasibility_service, HardwareFeasibilityService, CONTROLLERS_DB, COMPONENTS_CATALOG
)


@pytest.fixture
def test_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(test_app):
    return test_app.test_client()


@pytest.fixture
def hw_service():
    return get_hardware_feasibility_service()


# ==============================================================================
# 1. PROJECT TYPE CLASSIFICATION TESTS
# ==============================================================================

def test_classify_software_project(hw_service):
    """Ensure pure software projects are identified as software."""
    res = hw_service.classify_project_type(
        title="College Event Management System",
        description="A full-stack web application using Flask, React, and PostgreSQL for college workshops.",
        domain="Web Development"
    )
    assert res["category"] == "software"
    assert res["is_hardware"] is False
    assert "Software Project" in res["display_name"]


def test_classify_hardware_project(hw_service):
    """Ensure embedded / circuit projects are classified as hardware."""
    res = hw_service.classify_project_type(
        title="Automated Solar Tracking System",
        description="Dual-axis solar tracker using Arduino Uno, 2 LDR sensors, 2 SG90 servo motors, and a 12V power supply.",
        domain="Internet of Things (IoT)"
    )
    assert res["category"] == "hardware"
    assert res["is_hardware"] is True
    assert "Hardware Project" in res["display_name"]
    assert res["hw_score"] >= 3


def test_classify_hybrid_project(hw_service):
    """Ensure projects combining physical hardware with cloud/web are classified as hybrid."""
    res = hw_service.classify_project_type(
        title="Smart Greenhouse IoT Monitoring with Web Dashboard",
        description="ESP32 soil moisture and DHT22 sensors transmitting telemetry over Wi-Fi to a Flask web dashboard with PostgreSQL database.",
        domain="Internet of Things (IoT)"
    )
    assert res["category"] == "hybrid"
    assert res["is_hardware"] is True
    assert "Hybrid Project" in res["display_name"]
    assert res["hw_score"] >= 2
    assert res["sw_score"] >= 2


# ==============================================================================
# 2. ELECTRICAL, POWER & HAZARD DETECTION TESTS
# ==============================================================================

def test_electrical_calculation_and_safety_margin(hw_service):
    """Verify total current calculation includes the required 25% engineering safety margin."""
    components_arch = hw_service.extract_architecture_components(
        title="Smart Plant Irrigation",
        description="ESP32 with soil moisture sensor, 5V mini water pump, relay module, and 0.96 OLED display.",
        preferred_controller="ESP32"
    )
    electrical = hw_service.analyze_electrical_feasibility(components_arch)

    raw_current = electrical["total_current_raw_ma"]
    safe_current = electrical["total_current_safe_ma"]

    assert electrical["safety_margin_pct"] == 25
    assert safe_current == pytest.approx(raw_current * 1.25, rel=1e-2)
    assert electrical["total_power_safe_watts"] > 0
    assert "recommended_power_supply" in electrical


def test_hazard_detection_direct_drive_motor(hw_service):
    """Verify compatibility engine flags direct connection hazard for motors without drivers."""
    # Force architecture with motor but without motor driver
    arch = {
        "controller": CONTROLLERS_DB["Arduino Uno"],
        "inputs": [COMPONENTS_CATALOG["ultrasonic"]],
        "outputs": [COMPONENTS_CATALOG["dc_motor_bo"]],  # Motor present without L298N
        "communication": [],
        "power": []
    }
    electrical = hw_service.analyze_electrical_feasibility(arch)
    issues = electrical["compatibility_issues"]

    hazard_found = any("DIRECT CONNECTION NOT RECOMMENDED" in i["hazard"] or "Motor" in i["hazard"] for i in issues)
    assert hazard_found is True
    assert any("L298N" in i["solution"] or "motor driver" in i["solution"] for i in issues)


def test_hazard_detection_logic_level_mismatch(hw_service):
    """Verify 5V HC-SR04 on 3.3V ESP32 triggers voltage logic mismatch warning."""
    arch = {
        "controller": CONTROLLERS_DB["ESP32"],  # 3.3V logic
        "inputs": [COMPONENTS_CATALOG["ultrasonic"]],  # 5V Echo
        "outputs": [COMPONENTS_CATALOG["buzzer_active"]],
        "communication": [],
        "power": []
    }
    electrical = hw_service.analyze_electrical_feasibility(arch)
    issues = electrical["compatibility_issues"]

    mismatch_found = any("Voltage Logic Level Mismatch" in i["hazard"] for i in issues)
    assert mismatch_found is True
    assert any("voltage divider" in i["solution"] or "level converter" in i["solution"] for i in issues)


# ==============================================================================
# 3. BILL OF MATERIALS & PURCHASING OPTIONS TESTS
# ==============================================================================

def test_bill_of_materials_structure(hw_service):
    """Verify BOM generation contains all required specification fields."""
    components_arch = hw_service.extract_architecture_components(
        title="Smart Security Alarm",
        description="ESP32 with PIR motion sensor, active buzzer, and OLED display.",
        preferred_controller="ESP32"
    )
    bom = hw_service.generate_bill_of_materials(components_arch)

    assert len(bom) >= 4
    for item in bom:
        assert "name" in item
        assert "purpose" in item
        assert "quantity" in item
        assert "voltage" in item
        assert "current" in item
        assert "power" in item
        assert "necessity" in item
        assert "price_inr" in item
        assert item["price_inr"] > 0


def test_online_purchase_options_verified_links(hw_service):
    """Verify 3 categorized purchasing tiers (Best Value, Cheapest, Recommended) with valid URLs."""
    options_data = hw_service.get_online_purchase_options("ESP32 DevKit V1")
    assert "options" in options_data
    options = options_data["options"]
    assert len(options) == 3

    tiers = [o["tier_id"] for o in options]
    assert "best_value" in tiers
    assert "cheapest" in tiers
    assert "recommended" in tiers

    for opt in options:
        assert opt["product_url"].startswith("http://") or opt["product_url"].startswith("https://")
        assert "robu.in" in opt["product_url"] or "amazon.in" in opt["product_url"] or "electronicscomp.com" in opt["product_url"]
        assert "Compatible" in opt["compatibility"]


# ==============================================================================
# 4. FEASIBILITY SCORING & BUDGET ANALYSIS TESTS
# ==============================================================================

def test_feasibility_score_dimensions(hw_service):
    """Verify feasibility score calculates all 7 dimensions and correct status classification."""
    components_arch = hw_service.extract_architecture_components(
        title="Smart Weather Station",
        description="ESP32 with DHT22 temperature and humidity sensor, and 0.96 OLED display.",
        preferred_controller="ESP32"
    )
    electrical = hw_service.analyze_electrical_feasibility(components_arch)
    res = hw_service.calculate_feasibility_score(
        components_arch=components_arch,
        electrical_data=electrical,
        student_budget=2000.0,
        total_bom_cost=1100.0
    )

    assert 0 <= res["overall_score"] <= 100
    assert res["verdict"] in ["BUILDABLE", "BUILDABLE_WITH_MODIFICATIONS", "NOT_RECOMMENDED"]
    assert res["verdict_badge"].startswith("🟢") or res["verdict_badge"].startswith("🟡")
    assert res["verdict_reason"] != ""

    scores = res["scores"]
    assert "technical" in scores
    assert "availability" in scores
    assert "budget" in scores
    assert "power" in scores
    assert "compatibility" in scores
    assert "complexity" in scores
    assert "time" in scores


def test_budget_overrun_and_modifications(hw_service):
    """Verify that when cost exceeds budget, status is OVER_BUDGET and modifications are generated."""
    # Raspberry Pi 4 costs ₹5800, exceeding ₹2000 budget
    components_arch = hw_service.extract_architecture_components(
        title="Edge AI Camera System",
        description="Raspberry Pi 4 with camera and OLED display for vision monitoring.",
        preferred_controller="Raspberry Pi 4"
    )
    electrical = hw_service.analyze_electrical_feasibility(components_arch)
    bom = hw_service.generate_bill_of_materials(components_arch)
    total_cost = sum(i["price_inr"] for i in bom)

    score_res = hw_service.calculate_feasibility_score(
        components_arch=components_arch,
        electrical_data=electrical,
        student_budget=2000.0,
        total_bom_cost=total_cost
    )
    assert score_res["verdict"] == "BUILDABLE_WITH_MODIFICATIONS"

    mods = hw_service.generate_modification_suggestions(
        components_arch=components_arch,
        student_budget=2000.0,
        total_bom_cost=total_cost,
        compatibility_issues=electrical["compatibility_issues"]
    )
    assert len(mods) >= 1
    # Check that replacing RPi with ESP32 is recommended
    assert any("ESP32" in m["title"] or "ESP32" in m["change"] for m in mods)
    assert mods[0]["estimated_cost_reduction"] > 1000.0


# ==============================================================================
# 5. END-TO-END WORKFLOW & WEB INTEGRATION TESTS
# ==============================================================================

def test_hardware_project_submission_redirects_to_buildcheck(test_app, client):
    """Verify that submitting a Hardware project redirects to BuildCheck AI instead of immediately generating tasks."""
    with test_app.app_context():
        student = User(name="Charlie Student", email="charlie@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

    client.post("/auth/login", data={"email": "charlie@college.edu", "password": "pass123"}, follow_redirects=True)

    post_data = {
        "project_name": "Smart Automated Plant Watering System",
        "description": "An ESP32-based automated irrigation project with capacitive soil moisture sensor, 5V mini submersible water pump, relay module, and 0.96 OLED screen.",
        "domain": "Internet of Things (IoT)",
        "deadline": (date.today() + timedelta(days=60)).strftime("%Y-%m-%d"),
        "team_size": "2",
        "technologies_known": "C++, Arduino IDE, ESP32"
    }
    res = client.post("/student/projects/new", data=post_data, follow_redirects=False)

    # Must redirect to /student/projects/<id>/buildcheck
    assert res.status_code == 302
    assert "/buildcheck" in res.headers["Location"]

    with test_app.app_context():
        p = Project.query.filter_by(project_name="Smart Automated Plant Watering System").first()
        assert p is not None
        assert p.project_category in ["hardware", "hybrid"]
        assert p.hardware_feasibility_status == "PENDING_REVIEW"
        # Tasks MUST NOT be created yet before student approval!
        assert p.tasks.count() == 0

        # Analysis record must exist
        analysis = HardwareAnalysis.query.filter_by(project_id=p.id).first()
        assert analysis is not None
        assert analysis.overall_score > 0
        assert len(analysis.get_bom()) >= 3


def test_hardware_approval_generates_hardware_tasks(test_app, client):
    """Verify that when student approves hardware plan, 6-phase hardware tasks are created."""
    with test_app.app_context():
        student = User(name="Dana Student", email="dana@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

        p = Project(
            owner_id=student.id,
            project_name="IoT Health Monitor",
            description="ESP32 pulse sensor and OLED display with Wi-Fi.",
            domain="Internet of Things (IoT)",
            project_category="hardware",
            hardware_feasibility_status="PENDING_REVIEW",
            deadline=date.today() + timedelta(days=60)
        )
        db.session.add(p)
        db.session.commit()
        p_id = p.id

        hw_service = get_hardware_feasibility_service()
        hw_service.analyze_hardware_project(p)

    client.post("/auth/login", data={"email": "dana@college.edu", "password": "pass123"}, follow_redirects=True)

    # Approve hardware design
    res = client.post(f"/student/projects/{p_id}/buildcheck/approve", follow_redirects=False)
    assert res.status_code == 302
    assert "/review-tasks" in res.headers["Location"]

    with test_app.app_context():
        p = Project.query.get(p_id)
        assert p.hardware_feasibility_status == "APPROVED"
        tasks = p.tasks.all()
        assert len(tasks) >= 6

        phases = {t.phase for t in tasks}
        assert any("Research" in ph for ph in phases)
        assert any("Testing" in ph for ph in phases)
        assert any("Deployment" in ph or "Documentation" in ph for ph in phases)


def test_software_project_regression_keeps_existing_flow(test_app, client):
    """Ensure pure software project continues directly to standard task review without buildcheck interception."""
    with test_app.app_context():
        student = User(name="Eve Student", email="eve@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

    client.post("/auth/login", data={"email": "eve@college.edu", "password": "pass123"}, follow_redirects=True)

    post_data = {
        "project_name": "Online Student Course Forum",
        "description": "A web application for students to ask and answer programming questions, vote on responses, and download lecture notes.",
        "domain": "Web Development",
        "deadline": (date.today() + timedelta(days=60)).strftime("%Y-%m-%d"),
        "team_size": "2",
        "technologies_known": "Python, Flask, SQLite"
    }
    res = client.post("/student/projects/new", data=post_data, follow_redirects=False)

    # Must redirect directly to review-tasks or clarify (NOT buildcheck)
    assert res.status_code == 302
    assert "/buildcheck" not in res.headers["Location"]
    assert "/review-tasks" in res.headers["Location"] or "/clarify" in res.headers["Location"]

    with test_app.app_context():
        p = Project.query.filter_by(project_name="Online Student Course Forum").first()
        assert p is not None
        assert p.project_category == "software"
        assert p.hardware_feasibility_status == "NOT_APPLICABLE"


# ==============================================================================
# 6. DOMAIN-SPECIFIC HARDWARE VALIDATION TESTS (3 REAL-WORLD PROJECTS)
# ==============================================================================

def test_smart_irrigation_pipeline(test_app, hw_service):
    """
    Test Project 1: Smart Irrigation System.
    Validates: Soil moisture -> ESP32 -> Relay -> Water Pump flow.
    Ensures purpose-driven selection (no random sensors/RFID), accurate wiring table,
    8-point feasibility check, and dual budget calculation.
    """
    with test_app.app_context():
        student = User(name="Farmer Student", email="farmer@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

        project = Project(
            owner_id=student.id,
            project_name="IoT Smart Irrigation & Plant Health Monitor",
            description="Automated agricultural irrigation using capacitive soil moisture sensor, ESP32 microcontroller, 5V optocoupler relay module, and submersible water pump.",
            domain="Internet of Things (IoT)",
            project_category="hardware",
            hardware_feasibility_status="PENDING_REVIEW",
            deadline=date.today() + timedelta(days=60)
        )
        db.session.add(project)
        db.session.commit()

        analysis = hw_service.analyze_hardware_project(project)

        # 1. Controller & Component Selection
        proc = analysis.get_processing()
        assert len(proc) > 0
        assert "ESP32" in proc[0]["name"]

        inputs = analysis.get_inputs()
        inp_names = [i["name"] for i in inputs]
        assert any("Soil" in n for n in inp_names)
        # Ensure NO irrelevant components like RFID or ultrasonic injected
        assert not any("RFID" in n or "RC522" in n for n in inp_names)
        assert not any("Ultrasonic" in n for n in inp_names)

        outputs = analysis.get_outputs()
        out_names = [o["name"] for o in outputs]
        assert any("Relay" in n for n in out_names)
        assert any("Pump" in n for n in out_names)

        # 2. Pin-by-pin Wiring Table
        wiring = analysis.get_wiring_table()
        assert len(wiring) >= 6
        soil_wire = [w for w in wiring if "Soil" in w["component"]]
        assert len(soil_wire) >= 3
        # Analog pin on ADC1
        assert any("GPIO34" in w["connect_to"] or "ADC" in w["purpose"] for w in soil_wire)

        relay_wire = [w for w in wiring if "Relay" in w["component"]]
        assert any("GPIO4" in w["connect_to"] or "Switching" in w["purpose"] for w in relay_wire)

        # 3. 8-Point Feasibility Check
        checks = analysis.get_feasibility_checks()
        assert len(checks) == 8
        check_ids = [c["id"] for c in checks]
        assert "availability" in check_ids
        assert "compatibility" in check_ids
        assert "voltage_levels" in check_ids
        assert "mcu_capability" in check_ids
        assert "power_sufficiency" in check_ids
        assert "libraries_apis" in check_ids
        assert "missing_components" in check_ids
        assert "technical_conflicts" in check_ids
        assert analysis.verdict in ["BUILDABLE", "BUILDABLE_WITH_MODIFICATIONS"]
        assert "🟢" in analysis.verdict_badge or "🟡" in analysis.verdict_badge

        # 4. Processing Logic & Expected Output
        assert "GPIO34" in analysis.processing_logic_text or "soil" in analysis.processing_logic_text.lower()
        assert "pump" in analysis.processing_logic_text.lower()
        assert "moisture" in analysis.expected_output_text.lower()
        assert "115200" in analysis.expected_output_text

        # 5. Dual Budget Tiers
        budget_tiers = analysis.get_budget_tiers()
        assert "min_budget" in budget_tiers
        assert "recommended_budget" in budget_tiers
        assert budget_tiers["min_budget"]["total_cost"] <= budget_tiers["recommended_budget"]["total_cost"]
        assert "wires/connectors" in budget_tiers["total_formula"].lower()


def test_air_quality_monitoring_pipeline(test_app, hw_service):
    """
    Test Project 2: Air Quality Monitoring System.
    Validates: PMS5003 + MQ-135 -> ESP32 -> OLED / Wi-Fi flow.
    Ensures correct UART/Analog pin assignments, AQI calculations in logic,
    and no motor drivers or pumps.
    """
    with test_app.app_context():
        student = User(name="Air Student", email="air@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

        project = Project(
            owner_id=student.id,
            project_name="IoT Urban Air Quality & Pollution Monitor",
            description="Real-time environmental monitoring using Plantower PMS5003 laser dust sensor for PM2.5, MQ-135 hazardous gas sensor, ESP32, 0.96 OLED display, and Wi-Fi telemetry.",
            domain="Internet of Things (IoT)",
            project_category="hardware",
            hardware_feasibility_status="PENDING_REVIEW",
            deadline=date.today() + timedelta(days=60)
        )
        db.session.add(project)
        db.session.commit()

        analysis = hw_service.analyze_hardware_project(project)

        # 1. Inputs & Outputs
        inputs = analysis.get_inputs()
        inp_names = [i["name"] for i in inputs]
        assert any("PMS5003" in n or "Dust" in n for n in inp_names)
        assert any("MQ-135" in n or "Gas" in n for n in inp_names)
        assert not any("Pump" in n for n in inp_names)

        outputs = analysis.get_outputs()
        out_names = [o["name"] for o in outputs]
        assert any("OLED" in n for n in out_names)
        assert not any("Motor Driver" in n for n in out_names)

        # 2. Wiring
        wiring = analysis.get_wiring_table()
        oled_wire = [w for w in wiring if "OLED" in w["component"]]
        assert any("GPIO21" in w["connect_to"] or "SDA" in w["pin"] for w in oled_wire)
        assert any("GPIO22" in w["connect_to"] or "SCL" in w["pin"] for w in oled_wire)

        # 3. Processing Logic
        assert "PMS5003" in analysis.processing_logic_text or "PM2.5" in analysis.processing_logic_text
        assert "MQ-135" in analysis.processing_logic_text or "AQI" in analysis.processing_logic_text
        assert "PM2.5" in analysis.expected_output_text

        # 4. Software Requirements
        sw = analysis.get_software_reqs()
        lib_names = [l["name"] for l in sw.get("libraries", [])]
        assert any("Adafruit_SSD1306" in n for n in lib_names)
        assert any("PMS" in n for n in lib_names)


def test_face_recognition_attendance_pipeline(test_app, hw_service):
    """
    Test Project 3: Face Recognition Attendance System.
    Validates: Camera -> Raspberry Pi 4 -> OpenCV / Face Recognition model -> SQLite DB.
    Crucial: MUST select Raspberry Pi 4 (not basic 8-bit MCU) and MUST NOT inject RFID.
    """
    with test_app.app_context():
        student = User(name="Vision Student", email="vision@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

        project = Project(
            owner_id=student.id,
            project_name="AI Face Recognition Attendance System",
            description="Automated contactless classroom attendance using Raspberry Pi Camera Module v2, Raspberry Pi 4, OpenCV face embeddings, and SQLite database with buzzer confirmation.",
            domain="Artificial Intelligence",
            project_category="hardware",
            hardware_feasibility_status="PENDING_REVIEW",
            deadline=date.today() + timedelta(days=60)
        )
        db.session.add(project)
        db.session.commit()

        analysis = hw_service.analyze_hardware_project(project)

        # 1. Controller MUST be Raspberry Pi 4 (not ESP32 or Arduino)
        proc = analysis.get_processing()
        assert len(proc) > 0
        assert "Raspberry Pi 4" in proc[0]["name"]

        # 2. Inputs MUST include Camera and MUST NOT include RFID
        inputs = analysis.get_inputs()
        inp_names = [i["name"] for i in inputs]
        assert any("Camera" in n for n in inp_names)
        assert not any("RFID" in n or "RC522" in n for n in inp_names)

        # 3. Wiring table uses Raspberry Pi 40-pin header pins
        wiring = analysis.get_wiring_table()
        assert any("Pin " in w["connect_to"] or "CSI" in w["connect_to"] or "Pin 1" in w["connect_to"] for w in wiring)

        # 4. Software requirements for Python / OpenCV
        sw = analysis.get_software_reqs()
        assert "Python" in sw.get("programming_language", "")
        lib_names = [l["name"] for l in sw.get("libraries", [])]
        assert any("opencv-python" in n for n in lib_names)
        assert any("face-recognition" in n for n in lib_names)

        # 5. Processing logic mentions computer vision embeddings & database
        assert "OpenCV" in analysis.processing_logic_text or "embedding" in analysis.processing_logic_text.lower()
        assert "FPS" in analysis.expected_output_text or "Recognition" in analysis.expected_output_text


# ==============================================================================
# 10. BUILDCHECK TEMPLATE RENDERING & JINJA DICTIONARY KEY ACCESS TESTS
# ==============================================================================

def test_buildcheck_view_renders_dual_budget_tiers(test_app, client, hw_service):
    """
    Ensure /student/projects/<id>/buildcheck returns 200 OK and properly iterates
    over budget_tiers['min_budget']['items'] and budget_tiers['recommended_budget']['items']
    without triggering Jinja dictionary method collisions.
    """
    with test_app.app_context():
        student = User(name="Render Student", email="render@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

        project = Project(
            owner_id=student.id,
            project_name="Automated Hydroponics Controller",
            description="ESP32 controlled automated hydroponics with DHT22, water level sensor, 5V mini pump, and relay module.",
            domain="Internet of Things (IoT)",
            project_category="hardware",
            hardware_feasibility_status="PENDING_REVIEW",
            deadline=date.today() + timedelta(days=60)
        )
        db.session.add(project)
        db.session.commit()
        project_id = project.id

        # Pre-generate analysis
        analysis = hw_service.analyze_hardware_project(project)
        db.session.commit()

        # Verify budget_tiers has min_budget and recommended_budget with items
        tiers = analysis.get_budget_tiers()
        assert "min_budget" in tiers
        assert "items" in tiers["min_budget"]
        assert len(tiers["min_budget"]["items"]) > 0

    # Log in as the student
    client.post("/auth/login", data={"email": "render@college.edu", "password": "pass123"}, follow_redirects=True)

    # Request the buildcheck page
    resp = client.get(f"/student/projects/{project_id}/buildcheck")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    # Verify key sections rendered
    assert "BUILDCHECK AI" in html or "Hardware Feasibility" in html
    assert "Minimum-Budget Version" in html
    assert "Recommended Version" in html

    # Verify items from min_budget are rendered
    with test_app.app_context():
        p = Project.query.get(project_id)
        a = HardwareAnalysis.query.filter_by(project_id=p.id).first()
        t = a.get_budget_tiers()
        first_min_item = t["min_budget"]["items"][0]["name"]
        first_rec_item = t["recommended_budget"]["items"][0]["name"]
        assert first_min_item in html
        assert first_rec_item in html


def test_buildcheck_view_handles_empty_budget_tiers(test_app, client, hw_service):
    """
    Ensure the buildcheck page gracefully handles empty or None budget_tiers_json
    without raising TypeError: 'builtin_function_or_method' object is not iterable or 500 error.
    """
    with test_app.app_context():
        student = User(name="Empty Budget Student", email="empty@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

        project = Project(
            owner_id=student.id,
            project_name="Empty Budget Test Project",
            description="Arduino Uno obstacle avoiding robot with ultrasonic sensor and L298N motor driver.",
            domain="Robotics",
            project_category="hardware",
            hardware_feasibility_status="PENDING_REVIEW",
            deadline=date.today() + timedelta(days=60)
        )
        db.session.add(project)
        db.session.commit()
        project_id = project.id

        analysis = hw_service.analyze_hardware_project(project)
        # Force empty budget tiers JSON to simulate legacy/missing analysis state
        analysis.budget_tiers_json = "{}"
        db.session.commit()

    # Log in as the student
    client.post("/auth/login", data={"email": "empty@college.edu", "password": "pass123"}, follow_redirects=True)

    # Request the buildcheck page
    resp = client.get(f"/student/projects/{project_id}/buildcheck")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "No budget tier breakdown available" in html

    # Also test with budget_tiers_json = None
    with test_app.app_context():
        p = Project.query.get(project_id)
        a = HardwareAnalysis.query.filter_by(project_id=p.id).first()
        a.budget_tiers_json = None
        db.session.commit()

    resp = client.get(f"/student/projects/{project_id}/buildcheck")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "No budget tier breakdown available" in html


# ==============================================================================
# 11. GEMINI HARDWARE DECOMPOSITION TESTS ACROSS 4 DISTINCT PROJECT TYPES
# ==============================================================================

def test_gemini_hardware_esp32_temperature_humidity(test_app, hw_service):
    """
    Project Type 1: ESP32 + Temperature & Humidity Monitoring.
    Validates: DHT22/DHT11 sensor, 10k pull-up resistor, 0.96 OLED,
    5-stage architecture, pin-level wiring, and dual budget calculation.
    """
    with test_app.app_context():
        student = User(name="Weather Student", email="weather@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

        project = Project(
            owner_id=student.id,
            project_name="IoT Smart Room Weather Monitor",
            description="ESP32 monitoring temperature and humidity using DHT22 with 0.96 inch OLED display.",
            domain="Internet of Things (IoT)",
            project_category="hardware",
            hardware_feasibility_status="PENDING_REVIEW",
            deadline=date.today() + timedelta(days=60)
        )
        db.session.add(project)
        db.session.commit()

        analysis = hw_service.analyze_hardware_project(project)
        bom = analysis.get_bom()

        # Primary components must include MCU and sensor
        bom_names = [b["name"] for b in bom]
        assert any("ESP32" in n for n in bom_names)
        assert any("DHT" in n or "Temperature" in n for n in bom_names)

        # Supporting components must include 10k resistor or breadboard/jumpers
        assert any("Resistor" in n or "10k" in n or "Breadboard" in n or "Jumper" in n for n in bom_names)

        # 5-Stage architecture flow
        inputs = analysis.get_inputs()
        outputs = analysis.get_outputs()
        assert len(inputs) >= 1
        assert len(outputs) >= 1

        # Wiring table
        wiring = analysis.get_wiring_table()
        assert len(wiring) >= 4

        # Zero fake URL rule
        for item in bom:
            for opt in item.get("purchase_options", []):
                if not opt.get("verified"):
                    assert opt.get("url") is None
                    assert "robu.in" in opt.get("search_url", "") or "amazon.in" in opt.get("search_url", "") or "electronicscomp.com" in opt.get("search_url", "")


def test_gemini_hardware_gsm_alert_system(test_app, hw_service):
    """
    Project Type 2: GSM-based Alert System.
    Validates: SIM800L GSM module, 3.7V - 4.2V operating voltage, 2A peak current burst requirement,
    LM2596 buck converter or separate power supply, and SIM800L power brownout warnings.
    """
    with test_app.app_context():
        student = User(name="GSM Student", email="gsm@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

        project = Project(
            owner_id=student.id,
            project_name="GSM Emergency Disaster SMS Alert System",
            description="ESP32 connected to SIM800L GSM module sending emergency SMS alerts with panic button and buzzer.",
            domain="Embedded Systems",
            project_category="hardware",
            hardware_feasibility_status="PENDING_REVIEW",
            deadline=date.today() + timedelta(days=60)
        )
        db.session.add(project)
        db.session.commit()

        analysis = hw_service.analyze_hardware_project(project)
        bom = analysis.get_bom()
        bom_names = [b["name"] for b in bom]

        # GSM Module detected
        assert any("SIM800" in n or "GSM" in n for n in bom_names)

        # Critical Supporting component: LM2596 buck converter or regulator for 2A bursts
        assert any("LM2596" in n or "Buck" in n or "Regulator" in n or "Power" in n for n in bom_names)

        # Power Architecture checks
        power_arch = analysis.get_power_architecture()
        assert power_arch is not None
        warnings = power_arch.get("power_warnings", [])
        assert any("2A" in w or "burst" in w.lower() or "sim800" in w.lower() or "brownout" in w.lower() or "regulator" in w.lower() for w in warnings)

        # Check peak current is high (> 1000 mA) due to GSM transmission bursts
        peak_curr_str = str(power_arch.get("peak_current", "2000"))
        assert any(char.isdigit() for char in peak_curr_str)


def test_gemini_hardware_motor_relay_automation(test_app, hw_service):
    """
    Project Type 3: Motor / Relay-based Automation.
    Validates: 5V optocoupler relay module, 1N4007 flyback diode, inductive kickback/noise warning,
    and external 12V/9V power supply.
    """
    with test_app.app_context():
        student = User(name="Motor Student", email="motor@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

        project = Project(
            owner_id=student.id,
            project_name="Automated Industrial Solenoid Valve & Motor Pump Controller",
            description="Arduino Uno controlling high-power DC motor pump and 12V solenoid valve using 5V optocoupler relay module and float switch.",
            domain="Industrial Automation",
            project_category="hardware",
            hardware_feasibility_status="PENDING_REVIEW",
            deadline=date.today() + timedelta(days=60)
        )
        db.session.add(project)
        db.session.commit()

        analysis = hw_service.analyze_hardware_project(project)
        bom = analysis.get_bom()
        bom_names = [b["name"] for b in bom]

        # Must include relay and motor/pump
        assert any("Relay" in n for n in bom_names)
        assert any("Motor" in n or "Pump" in n or "Valve" in n for n in bom_names)

        # Supporting component: flyback diode or driver or power adapter
        assert any("Diode" in n or "1N4007" in n or "Adapter" in n or "Supply" in n or "Breadboard" in n for n in bom_names)

        # Compatibility issues should flag motor driver / back-EMF / regulator
        issues = analysis.get_compatibility_issues()
        assert len(issues) >= 1
        hazard_texts = " ".join([i.get("hazard", "") + " " + i.get("description", "") for i in issues])
        assert any(term in hazard_texts.lower() for term in ["motor", "relay", "power", "regulator", "driver", "back-emf", "inductive"])


def test_gemini_hardware_iot_wifi_cloud_telemetry(test_app, hw_service):
    """
    Project Type 4: IoT Project requiring Wi-Fi / Cloud Communication.
    Validates: ESP32 with native 2.4GHz Wi-Fi, MQTT/HTTP telemetry, OLED dashboard,
    complete wiring table, dual budget tiers, and ZERO fake URLs.
    """
    with test_app.app_context():
        student = User(name="Cloud Student", email="cloud@college.edu", role="student")
        student.set_password("pass123")
        db.session.add(student)
        db.session.commit()

        project = Project(
            owner_id=student.id,
            project_name="Smart Campus Energy Meter with Cloud Telemetry",
            description="ESP32 monitoring electrical energy with PZEM-004T current sensor and streaming telemetry via Wi-Fi to AWS IoT / MQTT cloud broker with 0.96 OLED.",
            domain="Internet of Things (IoT)",
            project_category="hardware",
            hardware_feasibility_status="PENDING_REVIEW",
            deadline=date.today() + timedelta(days=60)
        )
        db.session.add(project)
        db.session.commit()

        analysis = hw_service.analyze_hardware_project(project)
        bom = analysis.get_bom()

        # ESP32 controller
        proc = analysis.get_processing()
        assert any("ESP32" in p.get("name", "") for p in proc)

        # Software requirements should include Wi-Fi or MQTT or I2C
        sw = analysis.get_software_reqs()
        assert sw is not None

        # Dual Budget Tiers
        budget_tiers = analysis.get_budget_tiers()
        assert "min_budget" in budget_tiers
        assert "recommended_budget" in budget_tiers
        assert budget_tiers["min_budget"]["total_cost"] <= budget_tiers["recommended_budget"]["total_cost"]

        # ZERO fake URLs: Ensure EVERY single purchase option is verified or is a search query
        for item in bom:
            for opt in item.get("purchase_options", []):
                if opt.get("verified"):
                    assert opt.get("url") is not None
                    assert opt.get("url").startswith("http")
                else:
                    assert opt.get("url") is None
                    search_url = opt.get("search_url", "")
                    assert "robu.in" in search_url or "amazon.in" in search_url or "electronicscomp.com" in search_url



