import parsimonious
import quantumsim.circuit as ct
import numpy as np
import functools

qasm_grammar = parsimonious.Grammar(r"""
        program = (qubit_spec)* nl (circuit_spec)+
        qubit_spec = "qubit " id nl
        circuit_spec = initall nl (gatelist)* meas
        initall = "init_all" nl
        gatelist = gate (more_gates)* nl
        more_gates = ("|" gate)

        gate = !meas ws* (two_qubit_gate / single_qubit_gate) ws*

        single_qubit_gate = gate_name ws arg
        two_qubit_gate = gate_name ws arg ws arg
        arg = ~"[A-Za-z0-9]+"
        gate_name = id

        meas = "RO " arg nl
        ws = " "+
        nl = (" " / "\n" / "\r")*
        text = (id / "|" / " " / "\t")*
        id = ~"[A-Za-z0-9]+"
        """)


sgl_qubit_gate_map = {
    "i": None,
    "my90": functools.partial(ct.RotateY, angle=-np.pi / 2),
    "y90": functools.partial(ct.RotateY, angle=np.pi / 2),
    "y180": functools.partial(ct.RotateY, angle=np.pi),
    "mx90": functools.partial(ct.RotateX, angle=-np.pi / 2),
    "x90": functools.partial(ct.RotateX, angle=np.pi / 2),
    "x180": functools.partial(ct.RotateX, angle=np.pi),
}

dbl_qubit_gate_map = {
    "cz": ct.CPhase
}


def dropnil(lst):
    return [a for a in lst if a is not None]

class QASMParser(parsimonious.NodeVisitor):

    def __init__(self, dt=(20, 40), t1=30000, t2=30000):
        self.grammar = qasm_grammar
        self.lines = []
        self.qubit_names = []

        self.t1, self.t2 = t1, t2

        self.timestep = 0

        self.circuits = []
        self.gates = []
        self.timestep_increment_sgl = dt[0]
        self.timestep_increment_dbl = dt[1]
        self.timestep_increment = min(dt[0], dt[1])

    def visit_qubit_spec(self, node, children):
        self.qubit_names.append(children[1])

    def visit_initall(self, node, children):
        self.timestep = 0
        self.current_circuit = ct.Circuit("Circuit # " + str(len(self.circuits)))
        for qb in self.qubit_names:
            self.current_circuit.add_qubit(qb, t1=self.t1, t2=self.t2)

    def visit_gatelist(self, node, children):
        self.timestep += self.timestep_increment
        self.timestep_increment = min(self.timestep_increment_dbl, self.timestep_increment_sgl)

    def visit_single_qubit_gate(self, node, children):
        gate_name, arg = dropnil(children)

        dt = self.timestep_increment_sgl

        gate_factory = sgl_qubit_gate_map[gate_name.lower()]
        if gate_factory is not None:
            gate = gate_factory(bit=arg, time=self.timestep + dt/2)
            self.current_circuit.add_gate(gate)

        self.timestep_increment = max(dt, self.timestep_increment)

    def visit_two_qubit_gate(self, node, children):
        gate_name, arg1, arg2 = dropnil(children)

        dt = self.timestep_increment_dbl
        gate_factory = dbl_qubit_gate_map[gate_name.lower()]
        gate = gate_factory(bit0=arg1, bit1=arg2, time=self.timestep + dt/2)
        self.current_circuit.add_gate(gate)
        self.timestep_increment = max(dt, self.timestep_increment)

    def visit_arg(self, node, children):
        if node.text not in self.qubit_names:
            raise RuntimeError("Qubit '" + node.text + "' undefined")
        return node.text

    def visit_id(self, node, children):
        return node.text

    def visit_meas(self, node, children):
        self.current_circuit.add_waiting_gates(tmin=0, tmax=self.timestep+self.timestep_increment_sgl)
        self.current_circuit.order()

        self.circuits.append(self.current_circuit)

    def generic_visit(self, node, children):
        pass
