"""Idle (90 f) and Walk (40 f, in place) for the Verdant Qilin, 30 fps, seamless loops."""
import math
import anim_kit as A
from anim_kit import S

LEG_PHASE = {'FL': 0.0, 'BR': 0.25, 'FR': 0.5, 'BL': 0.75}   # lateral-sequence walk


def make(arm, legbones):
    A.bind(arm)
    legs = {k: (u, l, f, LEG_PHASE[k]) for k, (u, l, f) in legbones.items()}
    A.add_leg_ik(legs, root='Root')
    pb = lambda n: arm.pose.bones[n]

    def tail_wave(f, n, amp, ph0=0.0, k=1):
        for i, b in enumerate(('Tail1', 'Tail2', 'Tail3', 'Tail4')):
            A.set_rot(b, ((0, 0, 1), amp * (0.6 + 0.35 * i) * S(f, n * 1.0 / k, ph0 - 0.09 * i)),
                      ((1, 0, 0), 0.5 * amp * (0.4 + 0.3 * i) * S(f, n * 1.0 / k, ph0 - 0.09 * i + 0.25)))

    def pose_idle(f, n):
        # breathing: torso rises/falls, chest + neck follow a beat later, head looks around slowly
        pb('Torso').location = A.world_loc('Torso', (0, 0, 0.07 * S(f, n, 0)))
        A.set_rot('Chest', ((1, 0, 0), -1.2 * S(f, n, 0.1)))
        A.set_rot('Neck1', ((1, 0, 0), 1.6 * S(f, n, 0.18)), ((0, 0, 1), 3.0 * S(f, n, 0.0)))
        A.set_rot('Neck2', ((1, 0, 0), 1.2 * S(f, n, 0.26)), ((0, 0, 1), 4.0 * S(f, n, 0.05)))
        A.set_rot('Head', ((1, 0, 0), 2.0 * S(f, n, 0.34)), ((0, 0, 1), 5.0 * S(f, n, 0.1)))
        tail_wave(f, n, 7.0)
        for k, (u, l, ft, ph) in legs.items():
            pb('IK_' + k).location = (0, 0, 0)           # feet stay planted

    def pose_walk(f, n):
        for k, (u, l, ft, ph) in legs.items():
            dy, dz = A.foot_offset((f / n + ph) % 1.0, stride=2.2, lift=0.75, duty=0.62)
            pb('IK_' + k).location = A.world_loc('IK_' + k, (0, dy, dz))
        pb('Torso').location = A.world_loc('Torso', (0.0, 0.0, 0.09 * S(f, n, 0.0) * 1.0 + 0.0))
        A.set_rot('Torso', ((0, 1, 0), 2.0 * S(f, n, 0.0)), ((0, 0, 1), 2.5 * S(f, n, 0.25)))
        A.set_rot('Chest', ((0, 0, 1), -2.5 * S(f, n, 0.25)), ((1, 0, 0), 1.5 * S(f, n, 0.5)))
        A.set_rot('Neck1', ((1, 0, 0), 2.5 * S(f, n, 0.62)), ((0, 0, 1), 2.0 * S(f, n, 0.25)))
        A.set_rot('Neck2', ((1, 0, 0), 2.0 * S(f, n, 0.7)))
        A.set_rot('Head', ((1, 0, 0), 2.5 * S(f, n, 0.8)), ((0, 0, 1), -2.0 * S(f, n, 0.25)))
        tail_wave(f, n, 10.0, 0.25)

    clips = [('Idle', 90, pose_idle, False), ('Walk', 40, pose_walk, False)]
    A.bake_clips(clips, legs)
