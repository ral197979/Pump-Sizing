import streamlit as st
import math

# --- Start of PumpSizingCalculator Class ---
class PumpSizingCalculator:
    def __init__(self, unit_system="imperial"):
        self.unit_system = unit_system.lower()
        if self.unit_system not in ["imperial", "si"]:
            raise ValueError("Unit system must be 'imperial' or 'si'.")

        self.inputs = {
            # General
            "fluid_sg": 1.0,
            "pump_efficiency": 0.70,
            # Flow Rate
            "flow_rate": None,
            # Static Heads
            "suction_static_head": None,
            "discharge_static_head": None,
            # Pressure Heads
            "suction_pressure": 0.0,
            "discharge_pressure": 0.0,
            # Suction Pipe
            "suction_pipe_length": 0.0,
            "suction_pipe_id": None,
            "suction_c_factor": 120,
            "suction_fittings": {},
            # Discharge Pipe
            "discharge_pipe_length": 0.0,
            "discharge_pipe_id": None,
            "discharge_c_factor": 120,
            "discharge_fittings": {},
        }

        # Equivalent Lengths for fittings in Pipe Diameters (L/D)
        self.fitting_equivalent_lengths_D = {
            "gate_valve_open": 8,
            "globe_valve_open": 340,
            "check_valve_swing": 100,
            "check_valve_lift": 600,
            "45_elbow_std": 16,
            "90_elbow_std": 30,
            "90_elbow_long_radius": 20,
            "tee_branch": 60,
            "tee_run": 20,
            "foot_valve_strainer": 420,
            "entrance_sharp": 0.5,
            "exit_loss": 1.0,
        }
        self.results = {}

    def set_inputs(self, input_dict):
        for key, value in input_dict.items():
            if key in self.inputs:
                self.inputs[key] = value

    def _convert_flow_rate_for_hw(self, flow_rate):
        if self.unit_system == "imperial":
            return flow_rate
        else:
            return flow_rate / 3600

    def _get_hw_constants(self):
        if self.unit_system == "imperial":
            # D in FEET
            return 0.002083, 4.8655
        else:
            # D in METERS
            return 10.67, 4.8655

    def _calculate_friction_loss_hw(self, flow_rate, pipe_length, pipe_id, c_factor, fittings):
        if not all([flow_rate, pipe_id, c_factor]) or pipe_id <= 0:
            return 0.0

        Q_hw = self._convert_flow_rate_for_hw(flow_rate)
        K_hw, D_exp = self._get_hw_constants()

        total_equivalent_length = pipe_length
        for fitting_type, quantity in fittings.items():
            l_d_ratio = self.fitting_equivalent_lengths_D.get(fitting_type)
            if l_d_ratio and quantity > 0:
                if self.unit_system == "imperial":
                    equivalent_length = quantity * l_d_ratio * (pipe_id / 12.0)
                else:
                    equivalent_length = quantity * l_d_ratio * pipe_id
                total_equivalent_length += equivalent_length

        try:
            if c_factor == 0: raise ZeroDivisionError("C-Factor cannot be zero.")

            if self.unit_system == "imperial":
                D_for_formula = pipe_id / 12.0
            else:
                D_for_formula = pipe_id
            
            if D_for_formula == 0: raise ZeroDivisionError("Pipe ID cannot be zero.")

            hf = (K_hw * total_equivalent_length * (Q_hw / c_factor)**1.852) / (D_for_formula**D_exp)
            return hf
        except (ZeroDivisionError, ValueError) as e:
            st.error(f"Friction Loss Error: {e}")
            return float('inf')

    def calculate_pump_sizing(self):
        self.results = {}
        inputs = self.inputs
        Q, SG, pump_eff = inputs["flow_rate"], inputs["fluid_sg"], inputs["pump_efficiency"]
        Z1, Z2 = inputs["suction_static_head"], inputs["discharge_static_head"]
        P1, P2 = inputs["suction_pressure"], inputs["discharge_pressure"]

        for key, value in inputs.items():
            if value is None:
                raise ValueError(f"Input for '{key.replace('_', ' ')}' is missing.")
        
        pressure_conversion = (2.307 / SG) if self.unit_system == "imperial" else (0.102 / SG)
        P1_head = P1 * pressure_conversion
        P2_head = P2 * pressure_conversion

        hf_suction = self._calculate_friction_loss_hw(Q, inputs["suction_pipe_length"], inputs["suction_pipe_id"], inputs["suction_c_factor"], inputs["suction_fittings"])
        hf_discharge = self._calculate_friction_loss_hw(Q, inputs["discharge_pipe_length"], inputs["discharge_pipe_id"], inputs["discharge_c_factor"], inputs["discharge_fittings"])
        hf_total = hf_suction + hf_discharge
        
        TDH = (Z2 - Z1) + (P2_head - P1_head) + hf_total
        
        if self.unit_system == "imperial":
            power = (Q * TDH * SG) / (3960 * pump_eff) if pump_eff > 0 else float('inf')
            power_unit = "BHP"
        else:
            Q_m3_s = Q / 3600
            power = (Q_m3_s * TDH * (SG * 1000) * 9.81) / (pump_eff * 1000) if pump_eff > 0 else float('inf')
            power_unit = "kW"

        self.results = {
            "P1_head": P1_head, "P2_head": P2_head,
            "hf_suction": hf_suction, "hf_discharge": hf_discharge, "hf_total": hf_total,
            "TDH": TDH, "required_power": power, "power_unit": power_unit
        }

    def get_results_summary(self):
        if not self.results:
            return ["No results to display. Please run calculation."]

        unit_head = "feet" if self.unit_system == "imperial" else "meters"
        power_unit = self.results.get('power_unit', '')
        
        def format_val(value):
            return f"{value:.2f}" if isinstance(value, (int, float)) else str(value)

        summary = ["### Calculation Results"]
        summary.append(f"**Total Dynamic Head (TDH):** {format_val(self.results.get('TDH'))} {unit_head}")
        summary.append(f"**Required Power:** {format_val(self.results.get('required_power'))} {power_unit}")
        summary.append("---")
        summary.append("#### Head Breakdown")
        summary.append(f"**Total Friction Loss:** {format_val(self.results.get('hf_total'))} {unit_head}")
        summary.append(f" •  _Suction Loss:_ {format_val(self.results.get('hf_suction'))} {unit_head}")
        summary.append(f" •  _Discharge Loss:_ {format_val(self.results.get('hf_discharge'))} {unit_head}")
        
        return summary

# --- Streamlit UI Code ---
st.set_page_config(layout="wide", page_title="Pump Sizing Calculator")
st.title("🌊 Pump Sizing Calculator")
st.markdown("Enter your system parameters to calculate the Total Dynamic Head (TDH) and required pump power.")
st.markdown("---")

# --- Inputs Column ---
with st.sidebar:
    st.header("⚙️ System Inputs")
    unit_system_choice = st.radio("Unit System", ("Imperial", "SI"), horizontal=True)
    
    # Instantiate calculator
    calculator = PumpSizingCalculator(unit_system_choice.lower())

    # Define units based on choice
    unit_head = "ft" if unit_system_choice == "Imperial" else "m"
    unit_flow = "GPM" if unit_system_choice == "Imperial" else "m³/hr"
    unit_pressure = "psi" if unit_system_choice == "Imperial" else "kPa"
    unit_pipe_id = "in" if unit_system_choice == "Imperial" else "m"
    unit_length = "ft" if unit_system_choice == "Imperial" else "m"
    
    # Collect inputs
    inputs = {}
    st.subheader("General")
    inputs["flow_rate"] = st.number_input(f"Flow Rate ({unit_flow})", min_value=0.0, value=100.0)
    inputs["fluid_sg"] = st.number_input("Fluid Specific Gravity", min_value=0.1, value=1.0)
    inputs["pump_efficiency"] = st.slider("Pump Efficiency (%)", 1, 100, 75) / 100.0

    st.subheader("Elevation & Pressure")
    inputs["suction_static_head"] = st.number_input(f"Suction Elevation (Z1) ({unit_head})", value=5.0)
    inputs["discharge_static_head"] = st.number_input(f"Discharge Elevation (Z2) ({unit_head})", value=50.0)
    inputs["suction_pressure"] = st.number_input(f"Suction Pressure (P1) ({unit_pressure})", value=0.0)
    inputs["discharge_pressure"] = st.number_input(f"Discharge Pressure (P2) ({unit_pressure})", value=0.0)

# --- Pipe Details Columns ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("Suction Line Details")
    inputs["suction_pipe_length"] = st.number_input(f"Pipe Length ({unit_length})", key="s_len", value=20.0, min_value=0.0)
    inputs["suction_pipe_id"] = st.number_input(f"Internal Diameter ({unit_pipe_id})", key="s_id", value=6.0, min_value=0.001, format="%.3f")
    inputs["suction_c_factor"] = st.number_input("Hazen-Williams C-Factor", key="s_c", value=130, min_value=1)
    
    with st.expander("Add Suction Fittings"):
        suction_fittings = {}
        for fit_key, l_d in calculator.fitting_equivalent_lengths_D.items():
            qty = st.number_input(f"{fit_key.replace('_',' ').title()}", key=f"s_fit_{fit_key}", min_value=0, value=0)
            if qty > 0:
                suction_fittings[fit_key] = qty
        inputs["suction_fittings"] = suction_fittings

with col2:
    st.subheader("Discharge Line Details")
    inputs["discharge_pipe_length"] = st.number_input(f"Pipe Length ({unit_length})", key="d_len", value=100.0, min_value=0.0)
    inputs["discharge_pipe_id"] = st.number_input(f"Internal Diameter ({unit_pipe_id})", key="d_id", value=4.0, min_value=0.001, format="%.3f")
    inputs["discharge_c_factor"] = st.number_input("Hazen-Williams C-Factor", key="d_c", value=120, min_value=1)

    with st.expander("Add Discharge Fittings"):
        discharge_fittings = {}
        for fit_key, l_d in calculator.fitting_equivalent_lengths_D.items():
            qty = st.number_input(f"{fit_key.replace('_',' ').title()}", key=f"d_fit_{fit_key}", min_value=0, value=0)
            if qty > 0:
                discharge_fittings[fit_key] = qty
        inputs["discharge_fittings"] = discharge_fittings

# --- Calculation and Display ---
if st.sidebar.button("Calculate Pump Sizing", type="primary", use_container_width=True):
    try:
        calculator.set_inputs(inputs)
        calculator.calculate_pump_sizing()
        results_summary = calculator.get_results_summary()
        for line in results_summary:
            st.markdown(line, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"**Error:** {e}")
