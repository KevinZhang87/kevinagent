#!/usr/bin/env python3
"""
Healthcare Medical Device Cyberattack Surface Modeling
=====================================================
A comprehensive framework for modeling and analyzing cybersecurity 
attack surfaces in healthcare environments, focusing on medical devices.
"""

import json
import networkx as nx
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime


class ThreatCategory(Enum):
    """STRIDE threat categories for medical devices"""
    SPOOFING = "Spoofing"
    TAMPERING = "Tampering"
    REPUDIATION = "Repudiation"
    INFORMATION_DISCLOSURE = "Information Disclosure"
    DENIAL_OF_SERVICE = "Denial of Service"
    ELEVATION_OF_PRIVILEGE = "Elevation of Privilege"


class DeviceRiskLevel(Enum):
    """Risk levels based on FDA classification"""
    CLASS_I = "Class I - Low Risk"
    CLASS_II = "Class II - Moderate Risk" 
    CLASS_III = "Class III - High Risk"
    LIFE_SUPPORTING = "Life-Supporting"
    IMPLANTABLE = "Implantable"


class AttackVector(Enum):
    """Common attack vectors for medical devices"""
    NETWORK = "Network-based"
    PHYSICAL = "Physical access"
    WIRELESS = "Wireless/Radio"
    SOFTWARE = "Software/OS"
    FIRMWARE = "Firmware"
    SUPPLY_CHAIN = "Supply Chain"
    HUMAN_FACTOR = "Human Factor"
    API = "API/Interface"


@dataclass
class MedicalDevice:
    """Represents a medical device in the healthcare environment"""
    device_id: str
    name: str
    manufacturer: str
    device_type: str
    risk_level: DeviceRiskLevel
    network_connected: bool
    wireless_enabled: bool
    software_version: str
    os_type: Optional[str] = None
    firmware_version: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    protocols: List[str] = field(default_factory=list)
    data_types: List[str] = field(default_factory=list)
    vulnerabilities: List[str] = field(default_factory=list)
    last_patch_date: Optional[datetime] = None


@dataclass
class AttackSurface:
    """Represents the attack surface of a healthcare system"""
    surface_id: str
    name: str
    devices: List[MedicalDevice]
    network_segments: List[str]
    entry_points: List[str]
    data_flows: List[Dict]
    trust_boundaries: List[str]
    external_interfaces: List[str]
    attack_vectors: List[AttackVector]
    threat_categories: List[ThreatCategory]
    risk_score: float = 0.0
    vulnerabilities_count: int = 0


class HealthcareAttackSurfaceModeler:
    """
    Main class for modeling cyberattack surfaces in healthcare environments
    """
    
    def __init__(self):
        self.devices = {}
        self.attack_surfaces = {}
        self.threat_graph = nx.DiGraph()
        self.risk_matrix = {}
        self.mitigation_strategies = {}
        
    def add_medical_device(self, device: MedicalDevice):
        """Add a medical device to the model"""
        self.devices[device.device_id] = device
        print(f"Added device: {device.name} ({device.device_id})")
        
    def calculate_device_risk_score(self, device: MedicalDevice) -> float:
        """
        Calculate risk score for a medical device based on multiple factors
        
        Factors considered:
        - Risk level/classification
        - Network connectivity
        - Wireless capabilities
        - Vulnerability count
        - Patch status
        - Data sensitivity
        """
        risk_score = 0.0
        
        # Base risk from device classification
        risk_weights = {
            DeviceRiskLevel.CLASS_I: 1.0,
            DeviceRiskLevel.CLASS_II: 2.0,
            DeviceRiskLevel.CLASS_III: 3.0,
            DeviceRiskLevel.LIFE_SUPPORTING: 4.0,
            DeviceRiskLevel.IMPLANTABLE: 5.0
        }
        risk_score += risk_weights.get(device.risk_level, 1.0)
        
        # Network connectivity risk
        if device.network_connected:
            risk_score += 2.0
            if device.wireless_enabled:
                risk_score += 1.5
                
        # Vulnerability risk
        vulnerability_count = len(device.vulnerabilities)
        risk_score += vulnerability_count * 0.5
        
        # Patch status risk (if last patch > 90 days)
        if device.last_patch_date:
            days_since_patch = (datetime.now() - device.last_patch_date).days
            if days_since_patch > 90:
                risk_score += 2.0
            elif days_since_patch > 30:
                risk_score += 1.0
                
        # Data sensitivity risk
        sensitive_data_types = ["PHI", "PII", "Clinical", "Imaging", "Vital Signs"]
        sensitive_data = [d for d in device.data_types if d in sensitive_data_types]
        risk_score += len(sensitive_data) * 0.3
        
        # Protocol risk
        risky_protocols = ["Telnet", "FTP", "HTTP", "SNMPv1", "DICOM"]
        risky_count = len([p for p in device.protocols if p in risky_protocols])
        risk_score += risky_count * 0.4
        
        return round(risk_score, 2)
    
    def identify_attack_vectors(self, device: MedicalDevice) -> List[AttackVector]:
        """Identify potential attack vectors for a medical device"""
        vectors = []
        
        if device.network_connected:
            vectors.append(AttackVector.NETWORK)
            
        if device.wireless_enabled:
            vectors.append(AttackVector.WIRELESS)
            
        if device.os_type:
            vectors.append(AttackVector.SOFTWARE)
            
        if device.firmware_version:
            vectors.append(AttackVector.FIRMWARE)
            
        # Always consider physical access and human factors
        vectors.append(AttackVector.PHYSICAL)
        vectors.append(AttackVector.HUMAN_FACTOR)
        
        # Check for API/interface exposure
        if device.protocols:
            vectors.append(AttackVector.API)
            
        return vectors
    
    def generate_stride_threats(self, device: MedicalDevice) -> Dict[ThreatCategory, List[str]]:
        """
        Generate STRIDE threats for a medical device
        
        STRIDE Framework:
        - Spoofing: Impersonating something/someone
        - Tampering: Modifying data or code
        - Repudiation: Claiming to not have performed an action
        - Information Disclosure: Exposing information to unauthorized individuals
        - Denial of Service: Denying or degrading service to valid users
        - Elevation of Privilege: Gaining capabilities without proper authorization
        """
        threats = {}
        
        # Spoofing threats
        spoofing_threats = []
        if device.network_connected:
            spoofing_threats.extend([
                "IP spoofing to gain unauthorized access",
                "ARP spoofing to intercept communications",
                "Device impersonation on network"
            ])
        if device.wireless_enabled:
            spoofing_threats.extend([
                "Rogue access point attacks",
                "Bluetooth pairing spoofing",
                "RFID cloning attacks"
            ])
        if spoofing_threats:
            threats[ThreatCategory.SPOOFING] = spoofing_threats
            
        # Tampering threats
        tampering_threats = [
            "Firmware modification attacks",
            "Software update manipulation",
            "Configuration tampering"
        ]
        if device.network_connected:
            tampering_threats.extend([
                "Man-in-the-middle attacks",
                "Data injection attacks",
                "Protocol manipulation"
            ])
        threats[ThreatCategory.TAMpering] = tampering_threats
        
        # Information Disclosure threats
        info_disclosure_threats = [
            "Patient data exposure",
            "Device configuration leakage",
            "Diagnostic data interception"
        ]
        if device.network_connected:
            info_disclosure_threats.extend([
                "Network traffic sniffing",
                "Credential theft",
                "API endpoint enumeration"
            ])
        threats[ThreatCategory.INFORMATION_DISCLOSURE] = info_disclosure_threats
        
        # Denial of Service threats
        dos_threats = [
            "Resource exhaustion attacks",
            "Flood attacks on device interfaces",
            "Logic bomb activation"
        ]
        if device.network_connected:
            dos_threats.extend([
                "Network-based DDoS",
                "Protocol abuse leading to crashes",
                "Memory corruption attacks"
            ])
        threats[ThreatCategory.DENIAL_OF_SERVICE] = dos_threats
        
        # Elevation of Privilege threats
        eop_threats = [
            "Privilege escalation via vulnerabilities",
            "Default credential exploitation",
            "Weak authentication bypass"
        ]
        if device.os_type:
            eop_threats.extend([
                "OS-level privilege escalation",
                "Kernel exploits",
                "Service account compromise"
            ])
        threats[ThreatCategory.ELEVATION_OF_PRIVILEGE] = eop_threats
        
        return threats
    
    def create_attack_surface(self, name: str, devices: List[str], 
                            network_segments: List[str],
                            external_interfaces: List[str]) -> AttackSurface:
        """
        Create a comprehensive attack surface model
        
        Args:
            name: Name of the attack surface
            devices: List of device IDs to include
            network_segments: Network segments to consider
            external_interfaces: External interfaces to the system
        """
        device_objects = [self.devices[d] for d in devices if d in self.devices]
        
        # Calculate aggregate risk
        risk_scores = [self.calculate_device_risk_score(d) for d in device_objects]
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0
        
        # Count total vulnerabilities
        total_vulns = sum(len(d.vulnerabilities) for d in device_objects)
        
        # Identify all attack vectors
        all_vectors = set()
        for device in device_objects:
            vectors = self.identify_attack_vectors(device)
            all_vectors.update(vectors)
            
        attack_surface = AttackSurface(
            surface_id=f"as_{len(self.attack_surfaces) + 1}",
            name=name,
            devices=device_objects,
            network_segments=network_segments,
            entry_points=external_interfaces,
            data_flows=[],
            trust_boundaries=[],
            external_interfaces=external_interfaces,
            attack_vectors=list(all_vectors),
            threat_categories=list(ThreatCategory),
            risk_score=avg_risk,
            vulnerabilities_count=total_vulns
        )
        
        self.attack_surfaces[attack_surface.surface_id] = attack_surface
        return attack_surface
    
    def build_threat_graph(self, attack_surface_id: str):
        """
        Build a threat graph showing relationships between assets, 
        threats, and attack vectors
        """
        if attack_surface_id not in self.attack_surfaces:
            raise ValueError(f"Attack surface {attack_surface_id} not found")
            
        surface = self.attack_surfaces[attack_surface_id]
        
        # Clear existing graph
        self.threat_graph = nx.DiGraph()
        
        # Add device nodes
        for device in surface.devices:
            self.threat_graph.add_node(
                device.device_id,
                type="device",
                label=device.name,
                risk_level=device.risk_level.value
            )
            
        # Add network segment nodes
        for segment in surface.network_segments:
            self.threat_graph.add_node(
                segment,
                type="network",
                label=segment
            )
            
        # Add external interface nodes
        for interface in surface.external_interfaces:
            self.threat_graph.add_node(
                interface,
                type="external",
                label=interface
            )
            
        # Add threat nodes and edges
        for device in surface.devices:
            threats = self.generate_stride_threats(device)
            for category, threat_list in threats.items():
                threat_node = f"threat_{device.device_id}_{category.value}"
                self.threat_graph.add_node(
                    threat_node,
                    type="threat",
                    category=category.value,
                    threat_count=len(threat_list)
                )
                self.threat_graph.add_edge(device.device_id, threat_node, 
                                         relationship="has_threat")
                
    def visualize_attack_surface(self, attack_surface_id: str, 
                                filename: str = "attack_surface.png"):
        """Visualize the attack surface as a network graph"""
        if attack_surface_id not in self.attack_surfaces:
            raise ValueError(f"Attack surface {attack_surface_id} not found")
            
        surface = self.attack_surfaces[attack_surface_id]
        
        # Create a new graph for visualization
        G = nx.Graph()
        
        # Add nodes with attributes
        node_colors = []
        node_sizes = []
        
        for device in surface.devices:
            G.add_node(device.device_id, label=device.name[:20])
            node_colors.append('lightblue')
            node_sizes.append(1000)
            
        for segment in surface.network_segments:
            G.add_node(segment, label=segment[:20])
            node_colors.append('lightgreen')
            node_sizes.append(800)
            
        for interface in surface.external_interfaces:
            G.add_node(interface, label=interface[:20])
            node_colors.append('lightyellow')
            node_sizes.append(800)
            
        # Add edges (simplified - in reality you'd trace actual connections)
        device_ids = [d.device_id for d in surface.devices]
        for i in range(len(device_ids)):
            for j in range(i+1, len(device_ids)):
                G.add_edge(device_ids[i], device_ids[j])
                
        # Draw the graph
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(G, seed=42)
        
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, 
                              node_size=node_sizes, alpha=0.8)
        nx.draw_networkx_edges(G, pos, alpha=0.5)
        nx.draw_networkx_labels(G, pos, font_size=8)
        
        plt.title(f"Attack Surface: {surface.name}")
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"Attack surface visualization saved to {filename}")
        
    def generate_risk_report(self, attack_surface_id: str) -> Dict:
        """Generate a comprehensive risk report for an attack surface"""
        if attack_surface_id not in self.attack_surfaces:
            raise ValueError(f"Attack surface {attack_surface_id} not found")
            
        surface = self.attack_surfaces[attack_surface_id]
        
        report = {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "attack_surface": surface.name,
                "surface_id": attack_surface_id
            },
            "executive_summary": {
                "total_devices": len(surface.devices),
                "total_vulnerabilities": surface.vulnerabilities_count,
                "overall_risk_score": surface.risk_score,
                "risk_level": self._get_risk_level(surface.risk_score)
            },
            "device_analysis": [],
            "threat_analysis": {},
            "attack_vectors": [v.value for v in surface.attack_vectors],
            "recommendations": []
        }
        
        # Analyze each device
        for device in surface.devices:
            device_report = {
                "device_id": device.device_id,
                "name": device.name,
                "risk_level": device.risk_level.value,
                "risk_score": self.calculate_device_risk_score(device),
                "attack_vectors": [v.value for v in self.identify_attack_vectors(device)],
                "vulnerabilities": device.vulnerabilities,
                "threats": {}
            }
            
            # Generate STRIDE threats
            threats = self.generate_stride_threats(device)
            for category, threat_list in threats.items():
                device_report["threats"][category.value] = threat_list
                
            report["device_analysis"].append(device_report)
            
        # Generate recommendations
        report["recommendations"] = self._generate_recommendations(surface)
        
        return report
    
    def _get_risk_level(self, risk_score: float) -> str:
        """Convert risk score to risk level description"""
        if risk_score < 3.0:
            return "LOW"
        elif risk_score < 6.0:
            return "MEDIUM"
        elif risk_score < 8.0:
            return "HIGH"
        else:
            return "CRITICAL"
            
    def _generate_recommendations(self, surface: AttackSurface) -> List[str]:
        """Generate security recommendations based on attack surface analysis"""
        recommendations = []
        
        # Network security recommendations
        if AttackVector.NETWORK in surface.attack_vectors:
            recommendations.extend([
                "Implement network segmentation for medical devices",
                "Deploy intrusion detection systems (IDS) for medical device networks",
                "Establish secure network protocols (TLS 1.3, SSH)",
                "Implement zero-trust network architecture"
            ])
            
        # Wireless security recommendations
        if AttackVector.WIRELESS in surface.attack_vectors:
            recommendations.extend([
                "Implement WPA3 encryption for wireless medical devices",
                "Deploy wireless intrusion prevention systems",
                "Conduct regular wireless security assessments",
                "Implement Bluetooth Low Energy (BLE) security measures"
            ])
            
        # Software/firmware security recommendations
        if AttackVector.SOFTWARE in surface.attack_vectors or AttackVector.FIRMWARE in surface.attack_vectors:
            recommendations.extend([
                "Establish software bill of materials (SBOM) for all devices",
                "Implement secure boot and firmware verification",
                "Regular vulnerability scanning and patch management",
                "Code signing for all software updates"
            ])
            
        # General recommendations
        recommendations.extend([
            "Conduct regular penetration testing of medical device systems",
            "Implement comprehensive logging and monitoring",
            "Develop incident response plans for medical device compromises",
            "Provide security awareness training for clinical staff",
            "Establish vendor security assessment program",
            "Implement medical device security monitoring platform"
        ])
        
        return recommendations


def create_sample_healthcare_environment():
    """Create a sample healthcare environment for demonstration"""
    
    modeler = HealthcareAttackSurfaceModeler()
    
    # Create sample medical devices
    devices = [
        MedicalDevice(
            device_id="MRI_001",
            name="MRI Scanner",
            manufacturer="GE Healthcare",
            device_type="Imaging",
            risk_level=DeviceRiskLevel.CLASS_II,
            network_connected=True,
            wireless_enabled=True,
            software_version="4.2.1",
            os_type="Windows 10",
            firmware_version="2.1.3",
            ip_address="192.168.10.101",
            mac_address="00:1A:2B:3C:4D:5E",
            protocols=["DICOM", "HL7", "HTTPS"],
            data_types=["Imaging", "PHI", "Patient Demographics"],
            vulnerabilities=["CVE-2023-1234", "CVE-2023-5678"],
            last_patch_date=datetime(2023, 6, 15)
        ),
        MedicalDevice(
            device_id="IV_PUMP_001",
            name="Infusion Pump",
            manufacturer="Baxter",
            device_type="Infusion",
            risk_level=DeviceRiskLevel.CLASS_III,
            network_connected=True,
            wireless_enabled=True,
            software_version="3.0.2",
            firmware_version="1.5.0",
            ip_address="192.168.20.102",
            mac_address="00:2C:3D:4E:5F:6G",
            protocols=["HL7", "Proprietary"],
            data_types=["Infusion Data", "PHI"],
            vulnerabilities=["CVE-2022-9876"],
            last_patch_date=datetime(2023, 8, 20)
        ),
        MedicalDevice(
            device_id="PATIENT_MONITOR_001",
            name="Patient Monitor",
            manufacturer="Philips",
            device_type="Monitoring",
            risk_level=DeviceRiskLevel.CLASS_II,
            network_connected=True,
            wireless_enabled=True,
            software_version="5.1.0",
            os_type="Linux",
            firmware_version="3.2.1",
            ip_address="192.168.30.103",
            mac_address="00:3E:4F:5G:6H:7I",
            protocols=["HL7", "MQTT", "HTTPS"],
            data_types=["Vital Signs", "PHI", "Clinical"],
            vulnerabilities=[],
            last_patch_date=datetime(2023, 10, 5)
        ),
        MedicalDevice(
            device_id="VENTILATOR_001",
            name="Mechanical Ventilator",
            manufacturer="Medtronic",
            device_type="Life Support",
            risk_level=DeviceRiskLevel.LIFE_SUPPORTING,
            network_connected=True,
            wireless_enabled=False,
            software_version="2.3.4",
            firmware_version="1.8.2",
            ip_address="192.168.40.104",
            mac_address="00:4G:5H:6I:7J:8K",
            protocols=["HL7", "Proprietary"],
            data_types=["Ventilator Data", "PHI", "Clinical"],
            vulnerabilities=["CVE-2023-1111", "CVE-2023-2222", "CVE-2023-3333"],
            last_patch_date=datetime(2023, 3, 10)
        )
    ]
    
    # Add devices to modeler
    for device in devices:
        modeler.add_medical_device(device)
        
    # Create attack surface
    attack_surface = modeler.create_attack_surface(
        name="ICU Department Attack Surface",
        devices=["MRI_001", "IV_PUMP_001", "PATIENT_MONITOR_001", "VENTILATOR_001"],
        network_segments=["Medical Device VLAN", "Clinical VLAN", "Administrative VLAN"],
        external_interfaces=["Internet Gateway", "PACS System", "EMR Integration", "Remote Access VPN"]
    )
    
    return modeler, attack_surface


def main():
    """Main function to demonstrate attack surface modeling"""
    print("=" * 80)
    print("Healthcare Medical Device Cyberattack Surface Modeling")
    print("=" * 80)
    
    # Create sample environment
    modeler, attack_surface = create_sample_healthcare_environment()
    
    print(f"\n✓ Created attack surface: {attack_surface.name}")
    print(f"  - Devices: {len(attack_surface.devices)}")
    print(f"  - Network Segments: {len(attack_surface.network_segments)}")
    print(f"  - External Interfaces: {len(attack_surface.external_interfaces)}")
    print(f"  - Overall Risk Score: {attack_surface.risk_score}")
    print(f"  - Total Vulnerabilities: {attack_surface.vulnerabilities_count}")
    
    # Build threat graph
    modeler.build_threat_graph(attack_surface.surface_id)
    print(f"\n✓ Built threat graph with {len(modeler.threat_graph.nodes)} nodes "
          f"and {len(modeler.threat_graph.edges)} edges")
    
    # Generate risk report
    report = modeler.generate_risk_report(attack_surface.surface_id)
    
    print("\n" + "=" * 80)
    print("RISK REPORT SUMMARY")
    print("=" * 80)
    print(f"Overall Risk Level: {report['executive_summary']['risk_level']}")
    print(f"Overall Risk Score: {report['executive_summary']['overall_risk_score']}")
    print(f"Total Devices: {report['executive_summary']['total_devices']}")
    print(f"Total Vulnerabilities: {report['executive_summary']['total_vulnerabilities']}")
    
    print("\nTop Attack Vectors:")
    for vector in report['attack_vectors'][:5]:
        print(f"  - {vector}")
        
    print("\nTop Recommendations:")
    for i, rec in enumerate(report['recommendations'][:5], 1):
        print(f"  {i}. {rec}")
    
    # Save report to file
    with open('healthcare_risk_report.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n✓ Full report saved to healthcare_risk_report.json")
    
    # Generate visualization
    try:
        modeler.visualize_attack_surface(attack_surface.surface_id, "healthcare_attack_surface.png")
        print("✓ Attack surface visualization generated")
    except Exception as e:
        print(f"⚠ Could not generate visualization: {e}")
    
    # Demonstrate device-specific analysis
    print("\n" + "=" * 80)
    print("DEVICE-SPECIFIC ANALYSIS")
    print("=" * 80)
    
    for device in attack_surface.devices:
        risk_score = modeler.calculate_device_risk_score(device)
        attack_vectors = modeler.identify_attack_vectors(device)
        threats = modeler.generate_stride_threats(device)
        
        print(f"\n{device.name} ({device.device_id})")
        print(f"  Risk Level: {device.risk_level.value}")
        print(f"  Risk Score: {risk_score}")
        print(f"  Attack Vectors: {', '.join([v.value for v in attack_vectors])}")
        print(f"  STRIDE Threat Categories: {len(threats)}")
        
        # Count total threats
        total_threats = sum(len(t) for t in threats.values())
        print(f"  Total Identified Threats: {total_threats}")


if __name__ == "__main__":
    main()