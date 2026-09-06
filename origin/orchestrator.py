from collections import defaultdict
import time


class Origin_orch:
    """
    Stable Tiered Runtime:

    VM1 = Cold
    VM2 = Warm
    VM3 = Hot

    Features:
    - Persistent tier memory
    - Hysteresis thresholds
    - Migration cooldown to prevent thrashing
    """

    def __init__(self):

        # Execution tracking
        self.calls = defaultdict(int)
        self.time = defaultdict(float)

        # Persistent VM tier state
        self.tier = defaultdict(lambda: "VM1")

        # Last upgrade time (for cooldown)
        self.last_transition = defaultdict(lambda: 0)

        # Thresholds
        self.COLD_TO_WARM = 100
        self.WARM_TO_HOT = 1000

        # Cooldown (seconds or logical steps)
        self.COOLDOWN = 50

    # ----------------------------
    # Signature
    # ----------------------------
    def _sig(self, bytecode):
        return (len(bytecode), tuple(bytecode[:5]))

    # ----------------------------
    # Update stats
    # ----------------------------
    def _update(self, sig, dt):
        self.calls[sig] += 1
        self.time[sig] += dt

    # ----------------------------
    # Migration guard (prevents thrash)
    # ----------------------------
    def _can_transition(self, sig):
        return (self.calls[sig] - self.last_transition[sig]) > self.COOLDOWN

    # ----------------------------
    # Tier decision logic
    # ----------------------------
    def _select_vm(self, sig):

        calls = self.calls[sig]
        current = self.tier[sig]

        # No downgrade in V1 stability model
        if current == "VM3":
            return "VM3"

        # Upgrade rules (ONLY upward transitions)
        if current == "VM1":
            if calls > self.COLD_TO_WARM and self._can_transition(sig):
                self.tier[sig] = "VM2"
                self.last_transition[sig] = calls
            return self.tier[sig]

        if current == "VM2":
            if calls > self.WARM_TO_HOT and self._can_transition(sig):
                self.tier[sig] = "VM3"
                self.last_transition[sig] = calls
            return self.tier[sig]

        return current

    # ----------------------------
    # Main routing
    # ----------------------------
    def route(self, bytecode):

        sig = self._sig(bytecode)

        start = time.perf_counter()

        # Simulated execution cost
        time.sleep(len(bytecode) * 0.00001)

        dt = time.perf_counter() - start

        self._update(sig, dt)

        return self._select_vm(sig)

if __name__ == "__main__":
    orchestrator = Origin_orch()

    bytecode_sample = [1, 0, 3, 1, 2, 1, 1, 2, 4, 3, 1, 1, 3, 2, 1, 40, 4, 22, 1, 4, 3, 5, 2, 5, 41, 1, 6, 4, 3, 7, 1, 8, 2, 7, 40, 4, 22, 1, 9, 3, 10, 1, 11, 2, 10, 41, 40, 4, 22, 1, 12, 22, 1, 13, 22, 1, 0, 1, 14, 1, 15, 27, 3, 3, 16, 2, 16, 43, 44, 0, 83, 3, 17, 1, 18, 2, 17, 40, 4, 22, 20, 0, 68, 1, 12, 22, 1, 19, 22, 1, 20, 1, 21, 1, 22, 34, 2, 43, 44, 0, 113, 3, 23, 1, 24, 2, 23, 40, 4, 22, 20, 0, 98, 31]

    for i in range(1200):
        vm = orchestrator.route(bytecode_sample)
        if i % 200 == 0:
            print(f"Iteration {i} â†’ {vm}")

