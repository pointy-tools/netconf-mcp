You are the lead research-and-architecture planner for a project to build an **MCP server** that enables local coding agents to safely and effectively work with **NETCONF-enabled systems**. MCP servers can expose tools, resources, prompts, and server-provided instructions to clients, so the outcome should be an MCP design that teaches agents how to inspect device capabilities, reason about YANG schemas, and perform safe NETCONF workflows. ([Model Context Protocol][2])

Your mission is to produce a **deep research report and implementation plan** for a production-quality MCP server focused on NETCONF. Treat the work as **standards-first** and **security-first**. Use **primary sources first**: RFCs, IETF drafts only when clearly marked as non-final, official YANG modules, and official MCP specification/docs. Distinguish clearly between **normative RFC requirements**, **important operational conventions**, **vendor-specific behavior**, and **still-evolving drafts**. NETCONF itself is defined in RFC 6241; NETCONF over SSH in RFC 6242; TLS transport in RFC 7589; YANG 1.1 in RFC 7950; NMDA in RFC 8342; YANG Library in RFC 8525; monitoring in RFC 6022; NACM in RFC 8341; subscribed notifications in RFC 8639; and YANG-Push datastore updates in RFC 8641. ([IETF Datatracker][1])

#### Deliverables

Produce the following artifacts in one coherent output:

1. **Executive summary**
   Explain what NETCONF is, where it fits relative to CLI/screen-scraping and RESTCONF, and why an MCP server is a good control plane for AI agents. RESTCONF is an HTTP-based protocol over YANG datastores defined using NETCONF datastore concepts, so compare it carefully but keep the project centered on NETCONF first. ([RFC Editor][3])

2. **Standards map**
   Build a dependency map of the standards and specs that matter most for an implementation. At minimum cover:

   * RFC 6241 NETCONF base protocol
   * RFC 6242 NETCONF over SSH
   * RFC 7589 NETCONF over TLS
   * RFC 7950 YANG 1.1
   * RFC 8342 NMDA
   * RFC 8525 YANG Library
   * RFC 6022 NETCONF monitoring
   * RFC 8341 NACM
   * RFC 8639 subscribed notifications
   * RFC 8640 dynamic subscriptions over NETCONF
   * RFC 8641 YANG-Push datastore updates
   * RFC 8071 call home
   * RFC 6243 with-defaults
     Also identify any additional RFCs that are practically important for a first implementation, but separate “required now” from “later”. RFC 8640 provides the NETCONF binding for dynamic subscriptions of subscribed notifications and YANG-Push, and RFC 8071 defines NETCONF/RESTCONF Call Home. ([IETF Datatracker][4])

3. **NETCONF protocol decomposition**
   Explain, in implementation terms:

   * session establishment
   * `<hello>` exchange and capability discovery
   * message framing and protocol-version implications
   * RPC model
   * datastore model
   * locking semantics
   * edit workflow
   * validation / commit / confirmed-commit
   * filtering
   * error handling and error taxonomy
   * schema discovery
   * monitoring / observability
     NETCONF is XML/RPC-based, and NETCONF monitoring exposes sessions, locks, statistics, datastores, and schema discovery information. ([IETF Datatracker][1])

4. **Agent-facing abstraction design**
   Propose how raw NETCONF should be abstracted for LLM agents. Do **not** expose only low-level “send arbitrary XML” as the primary interface. Instead design a layered MCP interface:

   * safe high-level tools for common workflows
   * lower-level expert tools for controlled raw RPC access
   * resources that expose capabilities, YANG module inventory, datastore info, session state, recent errors, and device facts
   * reusable prompts that guide agents through discovery, read-only inspection, diff review, safe change planning, dry-run-like validation, and rollback-aware execution
     MCP supports tools, resources, prompts, and server-provided instructions; design around those primitives explicitly. ([Model Context Protocol][2])

5. **Proposed MCP server contract**
   Define a candidate MCP API surface, including:

   * tool names
   * tool arguments
   * return schemas
   * error schemas
   * example usage patterns
   * which operations should require explicit user confirmation
   * which operations should be read-only by default
   * how credentials and target inventory are referenced without leaking secrets into prompts
     Include recommended resources and prompts exposed by the server.

6. **Safety and security architecture**
   Design for least privilege, auditability, and blast-radius control. Address:

   * auth model for device access
   * secret storage and redaction
   * NACM-aware behavior
   * change approval gates
   * read-only default posture
   * allowlists for RPCs and YANG modules
   * schema validation before change attempts
   * lock handling
   * rollback / recovery
   * rate limiting / concurrency controls
   * transcript logging and tamper-evident audit trails
   * protections against prompt injection via device-returned text or schema metadata
   * secure MCP transport choices; for HTTP-based MCP auth, follow official MCP authorization/security guidance, while stdio-based local transports should rely on environment-based credential retrieval instead of that HTTP auth flow. ([IETF Datatracker][5])

7. **Schema and model strategy**
   Research how the MCP server should ingest and use YANG:

   * YANG Library discovery
   * module caching
   * revision handling
   * feature/deviation handling
   * schema normalization
   * vendor module support
   * translating YANG paths into agent-usable abstractions
   * when to prefer schema-driven editing versus template-driven editing
     YANG Library provides module, datastore, and schema information, including NMDA-aware datastore/schema listings. ([RFC Editor][6])

8. **Vendor interoperability strategy**
   Research likely differences across major NETCONF-capable platforms. Separate:

   * standard behavior expected from RFCs
   * common deviations
   * capability-based branching points
   * model support gaps
   * notification support differences
   * transaction/commit differences
     The output should recommend how the MCP server detects and adapts to per-device capability differences rather than hardcoding vendor assumptions. Capability and schema discovery are a first-class part of NETCONF and YANG Library. ([IETF Datatracker][1])

9. **Notifications and telemetry phase**
   Decide whether initial scope should include notifications and streaming telemetry. If yes, define a staged approach using the standards for subscribed notifications and YANG-Push; if no, justify deferring them. Subscribed notifications and YANG-Push are standardized separately from the base NETCONF protocol. ([IETF Datatracker][7])

10. **Implementation plan**
    Recommend:

    * language/runtime
    * NETCONF client libraries to evaluate
    * XML/YANG parsing stack
    * testing approach
    * simulated lab environment
    * conformance test strategy
    * packaging and local deployment model
    * milestone breakdown from prototype to hardened release
      Include a build-vs-buy view for any existing NETCONF libraries and for any existing MCP SDKs or reference servers. Official MCP examples include reference servers that demonstrate tools, resources, and prompts. ([Model Context Protocol][8])

11. **Concrete phased roadmap**
    Provide phases such as:

    * Phase 0: standards research and threat model
    * Phase 1: read-only discovery server
    * Phase 2: schema-aware config diff/planning
    * Phase 3: guarded write workflows
    * Phase 4: notifications / telemetry
    * Phase 5: multi-device orchestration
      For each phase, define scope, risks, acceptance criteria, and demo scenarios.

12. **Appendices**
    Include:

    * glossary
    * RFC reading order
    * open questions
    * assumptions
    * unresolved standards/draft areas
    * recommended test devices or simulators
    * example end-to-end agent workflows

#### Non-negotiable planning constraints

* Prefer **read-only discovery and reasoning** first; writes come later behind explicit safeguards.
* Do not treat vendor blog posts as authoritative when RFC text or official YANG says otherwise.
* Mark any use of Internet-Drafts as **non-final** and explain the implementation risk.
* Optimize for local-agent use: the MCP server should help an agent decide what is safe, supported, and schema-valid before any change is attempted.
* Assume real environments may have partial standards support, proprietary YANG modules, incomplete YANG Library data, and inconsistent capability advertisement.
* The plan must keep a clean separation between:

  * transport/session handling
  * NETCONF protocol engine
  * YANG/schema subsystem
  * policy/safety layer
  * MCP presentation layer
  * vendor adaptation layer
* Favor interfaces that return **structured data** over free-form text wherever possible.

#### Research method

Use this research method in order:

1. Start from the RFCs and official MCP docs.
2. Extract the minimum standards set needed for a useful first release.
3. Identify the hardest implementation questions and interoperability traps.
4. Build the MCP server surface around those realities, not around idealized protocol assumptions.
5. End with a prioritized action plan for implementation.

#### Required output style

Return the final answer as:

* a one-page executive summary
* a detailed standards matrix
* a proposed MCP server spec
* a phased implementation roadmap
* a risk register
* a list of open questions needing further experiments

If there is uncertainty, say so explicitly. If the standards leave room for interpretation, call it out. If a feature depends on an RFC beyond the base protocol, name that RFC clearly.
