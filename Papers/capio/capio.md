# Intro

A workflow describes a sequence of application steps and
their control/data dependencies. 

The ADIOS framework provides applications with a general I/O API to switch among multiple file-based or streaming-based transport backends
without paying the cost of rewriting the application code
for each one. However, it is not always desirable to rewrite or patch existing workflow steps to enable in situ orchestration by using ADIOS API or equivalent frameworks.

For this reason, we propose CAPIO, a new open-source middleware capable of transparently injecting streaming executions of I/O operations into traditional or in situ workflows to enable temporal parallelism among workflow steps and reduce the contention on the shared file system through memory-to-memory data transfer.

CAPIO shifts I/O coordination in workflows toward a declarative approach through a new, I/O-tailored coordination language based on the JSON syntax.

# Workflows
A workflow specification incorporates two different classes of semantics:  the host semantics, which defines the subprogram in each workflow step, and the coordination semantics, which defines the interactions between steps.

Tools in charge of exposing coordination semantics to the users
and orchestrating workflow executions are called Workflow Management Systems (WMSs)

# Optimize I/O behavior
The files are stored on a shared file system providing $wB$ and $rB$ write and read bandwidths that non-linearly depend on the file size. For the sake of simplicity, suppose that files are equally sized and bandwidth is constant. If $S$ writes files of size $N$ and $Q$ reads files of $M$ bytes, then the makespan $T_T$ depends on the compute time $T_C = T_C^S + T_C^Q$ and the total I/O time $T_{I/O} = T_{I/O}^S + T_{I/O}^Q$, such that:

$$\max(T_C, T_{I/O}) \leq T_T \leq T_C + T_{I/O} \tag{1}$$

$T_{I/O}$ is the total time spent producing and consuming the tokens in the workflow model. It can be described as:

$$T_{I/O} = k \cdot \left(\frac{N}{wB} + \frac{M}{rB}\right) \tag{2}$$

CAPIO approach for optimizing I/O in dataintensive workflows involves enhancing the in situ workflow model with I/O streaming behavior to overlap I/O and computation between consecutive steps.

# I/O Optimizations with CAPIO

Consider a two-step pipeline. A possible technique to shorten $T_{I/O}$ is to overlap the I/O phases of the two stages.

In the ideal case of full overlap, the equation can be rewritten
as follows:

$$T_{I/O} \approx \max\left(T_{I/O}^S, T_{I/O}^Q\right) = \max\left(\frac{kN}{wB}, \frac{kM}{rB}\right) \tag{3}$$

The challenge is introducing such streaming optimizations *without modifying the business code of the workflow steps involved*, which means reinterpreting the semantics of existing file access primitives rather than substituting them with semantically richer I/O calls (e.g., ADIOS).

The CAPIO user-space I/O middleware aims to enable these optimizations through: 
- Concurrent execution rather than batch execution of workflow steps for which the I/O operations have to be optimized.
- By enabling a more relaxed synchronization semantics for tokens propagation than the standard on-termination one (cf. Sec II-A).

# CAPIO Middleware
The CAPIO middleware is made of two logical tiers:
- The higher tier defines a coordination model allowing the user to express relaxed token synchronization semantics between producer-consumer workflow steps via an I/O coordination language (currently in the JSON format) describing when a file is fireable (i.e., when its content can be accessed) and when a file is committed (i.e., when it is completed).
- The lower tier implements the CAPIO runtime system, which comprises a set of per-node user-space servers implementing the distributed data and metadata storage for the files and directories and the intercept library.

# Commit and Firing rules
To define the file synchronization semantics between consecutive workflow steps, we should consider two temporal aspects (rules):
- Commit rule: When there are no more updates to the file.
- Firing rule: When a consumer can safely start reading (portion of) data written in the file. 