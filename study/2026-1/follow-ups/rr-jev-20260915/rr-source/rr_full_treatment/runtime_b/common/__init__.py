"""Common code shared by all three arms.

``architecture.arm_isolation`` permits every arm to import this package.  It
therefore imports neither ``rr_s_all_kernel`` nor ``receiver_reliance`` nor any
arm module, and nothing in it reaches the filesystem, the network, a subprocess,
a dynamic import or a reflection import.  The single exception is ``pins``,
which is the import-time dependency gate and is imported only by the two arms
that carry an accepted dependency.
"""
