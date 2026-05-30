#!/usr/bin/env python3
"""
Simplified Healthcare Attack Surface Modeling
"""

import json
from datetime import datetime
from typing import Dict, List

class SimpleMedicalDevice:
    def __init__(self, device_id, name, risk_level, network_connected=True):
        self.device_id = device_id
        self.name = name
        self.risk_level = risk_level
        self.network_connected = network_connected
        self.vulnerabilities = []
        self.attack_vectors = []
        
    def add_vulnerability(self, vuln):
        self.vulnerabilities.append(vuln)
        
    def add_attack_vector(self, vector):
        self.attack_vectors.append(vector)

def calculate_risk_score(device):
    """Calculate simple risk score"""
    base_score = 0
    
    # Risk level scoring
    risk_scores = {
        "Low": 1,
        "Medium": 2,
        "High": 3,
        "Critical": 4,
        "Life-Supporting": 5
    }
    base_score += risk_scores.get(device.risk_level, 1)
    
    # Network connectivity risk
    if device.network_connected:
        base_score += 2
        
    # Vulnerability risk
    base_score += len(device.vulnerabilities) * 0.5
    
    return base_score

def identify_threats(device):
    """Identify basic threats for a device"""
    threats = []
    
    if device.network_connected:
        threats.extend([
            "Network-based attacks",
            "Unauthorized remote access",
            "Data interception"
        ])
        
    if device.risk_level in ["High", "Critical", "Life-Supporting"]:
        threats.extend([
            "Device compromise affecting patient safety",
            "Ransomware attacks",
            "Supply chain attacks"
        ])
        
    return threats

def main():
    print("=" * 60)
    print("Healthcare Medical Device Attack Surface Analysis")
    print("=" * 60)
    
    # Create sample devices
    devices = [
        SimpleMedicalDevice("MRI_001", "MRI Scanner", "Medium", True),
        SimpleMedicalDevice("IV_001", "Infusion Pump", "Critical", True),
        SimpleMedicalDevice("MONITOR_001", "Patient Monitor", "Medium", True),
        SimpleMedicalDevice("VENT_001", "Ventilator", "Life-Supporting", True)
    ]
    
    # Add vulnerabilities
    devices[0].vulnerabilities = ["CVE-2023-1234", "CVE-2023-5678"]
    devices[1].vulnerabilities = ["CVE-2022-9876"]
    devices[3].vulnerabilities = ["CVE-2023-1111", "CVE-2023-2222", "CVE-2023-3333"]
    
    # Add attack vectors
    for device in devices:
        device.attack_vectors = ["Network", "Physical", "Software"]
        if device.risk_level == "Life-Supporting":
            device.attack_vectors.append("Firmware")
    
    print("\nDevice Analysis:")
    print("-" * 60)
    
    total_risk = 0
    all_threats = []
    
    for device in devices:
        risk_score = calculate_risk_score(device)
        threats = identify_threats(device)
        total_risk += risk_score
        all_threats.extend(threats)
        
        print(f"\n{device.name} ({device.device_id})")
        print(f"  Risk Level: {device.risk_level}")
        print(f"  Risk Score: {risk_score}")
        print(f"  Network Connected: {device.network_connected}")
        print(f"  Vulnerabilities: {len(device.vulnerabilities)}")
        print(f"  Attack Vectors: {', '.join(device.attack_vectors)}")
        print(f"  Identified Threats: {len(threats)}")
    
    print("\n" + "=" * 60)
    print("OVERALL ATTACK SURFACE SUMMARY")
    print("=" * 60)
    print(f"Total Devices: {len(devices)}")
    print(f"Total Risk Score: {total_risk}")
    print(f"Average Risk Score: {total_risk / len(devices):.2f}")
    print(f"Total Vulnerabilities: {sum(len(d.vulnerabilities) for d in devices)}")
    print(f"Total Identified Threats: {len(all_threats)}")
    
    # Count unique threats
    unique_threats = list(set(all_threats))
    print(f"Unique Threat Types: {len(unique_threats)}")
    
    # Generate attack surface map
    print("\nAttack Surface Map:")
    print("-" * 60)
    
    attack_surface = {
        "entry_points": [
            "Network interfaces",
            "Wireless connections", 
            "USB ports",
            "Serial ports",
            "Physical access"
        ],
        "trust_boundaries": [
            "Medical device network",
            "Clinical network",
            "Administrative network",
            "Internet boundary"
        ],
        "data_flows": [
            "Device to PACS (DICOM)",
            "Device to EMR (HL7)",
            "Device to Monitoring System",
            "Remote Management"
        ]
    }
    
    print("Entry Points:")
    for point in attack_surface["entry_points"]:
        print(f"  • {point}")
        
    print("\nTrust Boundaries:")
    for boundary in attack_surface["trust_boundaries"]:
        print(f"  • {boundary}")
        
    print("\nCritical Data Flows:")
    for flow in attack_surface["data_flows"]:
        print(f"  • {flow}")
    
    # STRIDE threat summary
    print("\n" + "=" * 60)
    print("STRIDE THREAT ANALYSIS")
    print("=" * 60)
    
    stride_threats = {
        "Spoofing": [
            "Device impersonation",
            "Credential theft",
            "Network spoofing attacks"
        ],
        "Tampering": [
            "Firmware modification",
            "Data manipulation",
            "Configuration changes"
        ],
        "Repudiation": [
            "Audit log tampering",
            "Action denial"
        ],
        "Information Disclosure": [
            "Patient data exposure",
            "Network traffic interception",
            "Configuration leakage"
        ],
        "Denial of Service": [
            "Network flooding",
            "Resource exhaustion",
            "Device crashes"
        ],
        "Elevation of Privilege": [
            "Privilege escalation",
            "Default credential abuse",
            "Unauthorized access"
        ]
    }
    
    for category, threats in stride_threats.items():
        print(f"\n{category}:")
        for threat in threats:
            print(f"  • {threat}")
    
    # Recommendations
    print("\n" + "=" * 60)
    print("SECURITY RECOMMENDATIONS")
    print("=" * 60)
    
    recommendations = [
        "Implement network segmentation for medical devices",
        "Deploy intrusion detection/prevention systems",
        "Establish regular vulnerability scanning program",
        "Implement secure firmware update mechanisms",
        "Conduct regular penetration testing",
        "Provide security awareness training for staff",
        "Develop incident response procedures",
        "Implement zero-trust architecture principles",
        "Establish vendor security assessment program",
        "Deploy medical device security monitoring"
    ]
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i:2}. {rec}")
    
    # Save results
    results = {
        "timestamp": datetime.now().isoformat(),
        "devices_analyzed": len(devices),
        "total_risk_score": total_risk,
        "average_risk_score": total_risk / len(devices),
        "total_vulnerabilities": sum(len(d.vulnerabilities) for d in devices),
        "attack_surface": attack_surface,
        "stride_threats": stride_threats,
        "recommendations": recommendations
    }
    
    with open("healthcare_attack_surface_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Results saved to healthcare_attack_surface_results.json")
    print("=" * 60)

if __name__ == "__main__":
    main()