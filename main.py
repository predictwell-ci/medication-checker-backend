from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
from pathlib import Path
from enum import Enum
import os

app = FastAPI(
    title="Medication Safety Checker",
    description="Comprehensive medication interaction and safety analysis system",
    version="1.0.0"
)

# CORS middleware - UPDATE THIS WITH YOUR NETLIFY URL AFTER DEPLOYMENT
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to ["https://your-site.netlify.app"] after deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SIMPLIFIED DATABASE LOADING - FIXED FOR RENDER
def load_database():
    """Load medication database - simplified for Render deployment"""
    try:
        # Try current directory first (Render's deployment location)
        with open('medications_database.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback to same directory as main.py
        base_dir = Path(__file__).parent
        db_path = base_dir / "medications_database.json"
        with open(db_path, 'r', encoding='utf-8') as f:
            return json.load(f)

# Load database
MEDICATION_DB = load_database()

class SeverityFlag(str, Enum):
    BLACK_FLAG = "BLACK_FLAG"  # Contraindicated/Deadly
    RED_FLAG = "RED_FLAG"      # Dangerous
    ORANGE_FLAG = "ORANGE_FLAG"  # Major Warning
    YELLOW_FLAG = "YELLOW_FLAG"  # Moderate Warning
    GREEN_FLAG = "GREEN_FLAG"  # Safe

class MedicationCheckRequest(BaseModel):
    medications: List[str]
    patient_age: Optional[int] = None
    patient_conditions: Optional[List[str]] = []

class InteractionDetail(BaseModel):
    drug_a: str
    drug_b: str
    severity: SeverityFlag
    mechanism: str
    description: str
    clinical_effects: str
    recommendation: str
    evidence_level: str
    source: str

class DrugProfile(BaseModel):
    name: str
    generic_name: str
    brand_names: List[str]
    drug_class: str
    black_box_warning: Optional[Dict[str, Any]]
    cyp_metabolism: List[str]
    contraindications: List[str]
    side_effects: List[str]

class SafetyAnalysisResponse(BaseModel):
    analyzed_medications: List[DrugProfile]
    interactions: List[InteractionDetail]
    black_flags: List[InteractionDetail]
    red_flags: List[InteractionDetail]
    orange_flags: List[InteractionDetail]
    yellow_flags: List[InteractionDetail]
    green_flags: List[InteractionDetail]
    overall_risk_level: str
    risk_summary: Dict[str, int]
    clinical_recommendations: List[str]

class MedicationSafetyEngine:
    def __init__(self):
        self.medications = {med["id"]: med for med in MEDICATION_DB["medications"]}
        self.interactions = MEDICATION_DB["interactions"]
    
    def find_medication(self, name: str) -> Optional[Dict]:
        """Find medication by name (case-insensitive, fuzzy match)"""
        name_lower = name.lower().strip()
        
        for med_id, med in self.medications.items():
            # Check exact matches
            if (med["name"].lower() == name_lower or 
                med["generic_name"].lower() == name_lower or
                any(brand.lower() == name_lower for brand in med["brand_names"])):
                return med
            
            # Check partial matches
            if (name_lower in med["name"].lower() or
                name_lower in med["generic_name"].lower() or
                any(name_lower in brand.lower() for brand in med["brand_names"])):
                return med
        
        return None
    
    def check_interactions(self, med_ids: List[str]) -> List[Dict]:
        """Check for interactions between medications"""
        found_interactions = []
        
        for interaction in self.interactions:
            drug_a_id = interaction["drug_a"]
            drug_b_id = interaction["drug_b"]
            
            if drug_a_id in med_ids and drug_b_id in med_ids:
                found_interactions.append(interaction)
        
        return found_interactions
    
    def analyze_medications(self, medication_names: List[str]) -> SafetyAnalysisResponse:
        """Main analysis function"""
        # Find all medications
        found_meds = []
        med_ids = []
        
        for name in medication_names:
            med = self.find_medication(name)
            if med:
                found_meds.append(med)
                med_ids.append(med["id"])
        
        if not found_meds:
            raise HTTPException(status_code=404, detail="No medications found in database")
        
        # Get interactions
        interactions = self.check_interactions(med_ids)
        
        # Categorize by severity
        black_flags = [i for i in interactions if i["severity"] == "BLACK_FLAG"]
        red_flags = [i for i in interactions if i["severity"] == "RED_FLAG"]
        orange_flags = [i for i in interactions if i["severity"] == "ORANGE_FLAG"]
        yellow_flags = [i for i in interactions if i["severity"] == "YELLOW_FLAG"]
        green_flags = [i for i in interactions if i["severity"] == "GREEN_FLAG"]
        
        # Calculate overall risk
        if black_flags:
            overall_risk = "CRITICAL - CONTRAINDICATED COMBINATION"
        elif red_flags:
            overall_risk = "HIGH - DANGEROUS COMBINATION"
        elif orange_flags:
            overall_risk = "MODERATE-HIGH - MAJOR WARNINGS"
        elif yellow_flags:
            overall_risk = "MODERATE - MONITOR CLOSELY"
        else:
            overall_risk = "LOW - GENERALLY SAFE"
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            found_meds, black_flags, red_flags, orange_flags
        )
        
        # Build response
        drug_profiles = []
        for med in found_meds:
            drug_profiles.append(DrugProfile(
                name=med["name"],
                generic_name=med["generic_name"],
                brand_names=med["brand_names"],
                drug_class=med["class"],
                black_box_warning=med.get("black_box_warning"),
                cyp_metabolism=med["cyp_metabolism"],
                contraindications=med["contraindications"],
                side_effects=med["side_effects"]
            ))
        
        return SafetyAnalysisResponse(
            analyzed_medications=drug_profiles,
            interactions=interactions,
            black_flags=black_flags,
            red_flags=red_flags,
            orange_flags=orange_flags,
            yellow_flags=yellow_flags,
            green_flags=green_flags,
            overall_risk_level=overall_risk,
            risk_summary={
                "total_medications": len(found_meds),
                "total_interactions": len(interactions),
                "black_flags": len(black_flags),
                "red_flags": len(red_flags),
                "orange_flags": len(orange_flags),
                "yellow_flags": len(yellow_flags),
                "green_flags": len(green_flags),
                "medications_with_black_box_warnings": len([m for m in found_meds if m.get("black_box_warning")])
            },
            clinical_recommendations=recommendations
        )
    
    def _generate_recommendations(self, medications, black_flags, red_flags, orange_flags):
        """Generate clinical recommendations"""
        recommendations = []
        
        if black_flags:
            recommendations.append("⚠️ CRITICAL: This combination is CONTRAINDICATED. Do NOT use together without specialist consultation.")
            for flag in black_flags:
                recommendations.append(f"   → {flag['recommendation']}")
        
        if red_flags:
            recommendations.append("⚠️ DANGEROUS: Serious interaction risk detected. Requires immediate medical review.")
            for flag in red_flags:
                recommendations.append(f"   → {flag['recommendation']}")
        
        if orange_flags:
            recommendations.append("⚠️ WARNING: Major interactions detected. Close monitoring required.")
            for flag in orange_flags:
                recommendations.append(f"   → {flag['recommendation']}")
        
        # Black box warnings
        bbw_meds = [m for m in medications if m.get("black_box_warning")]
        if bbw_meds:
            recommendations.append("⚫ BLACK BOX WARNINGS:")
            for med in bbw_meds:
                bbw = med["black_box_warning"]
                recommendations.append(f"   → {med['name']}: {bbw['warning']}")
        
        # General recommendations
        if black_flags or red_flags:
            recommendations.append("📋 General Recommendations:")
            recommendations.append("   • Consult prescribing physician or pharmacist immediately")
            recommendations.append("   • Do not start, stop, or change doses without medical supervision")
            recommendations.append("   • Monitor for signs of adverse effects")
            recommendations.append("   • Keep all healthcare providers informed of all medications")
        
        return recommendations

# Initialize engine
engine = MedicationSafetyEngine()

@app.get("/")
def root():
    return {
        "service": "Medication Safety Checker",
        "status": "operational",
        "version": "1.0.0",
        "capabilities": [
            "Drug-drug interaction detection",
            "Black box warning identification",
            "Severity-based risk assessment",
            "Clinical recommendations"
        ]
    }

@app.get("/healthz")
def health():
    return {"ok": True}

@app.post("/api/check", response_model=SafetyAnalysisResponse)
def check_medications(request: MedicationCheckRequest):
    """Check medication list for safety concerns"""
    try:
        result = engine.analyze_medications(request.medications)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/medications")
def list_medications():
    """List all medications in database"""
    return {
        "medications": [
            {
                "name": med["name"],
                "generic_name": med["generic_name"],
                "class": med["class"]
            }
            for med in MEDICATION_DB["medications"]
        ]
    }

@app.get("/api/medication/{med_name}")
def get_medication_info(med_name: str):
    """Get detailed information about a specific medication"""
    med = engine.find_medication(med_name)
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")
    return med

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
