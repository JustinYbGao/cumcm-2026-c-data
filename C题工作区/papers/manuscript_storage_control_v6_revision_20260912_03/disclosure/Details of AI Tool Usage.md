# Details of AI Tool Usage

Our team used AI for problem interpretation, discussion and implementation of models, data processing, code generation and debugging, computational experiments and result analysis, figure production, reference checking, substantive manuscript drafting, and layout review. Our team determined the final interpretation of the problem, modeling approach, adopted code, result analysis, and conclusions. The following sections describe the tools, purposes, principal interactions, and review of adopted outputs.

## 1 AI tools and models

We used the OpenAI Codex client with GPT-6 Astra and GPT-5.6 Luna. Through the client, we discussed the work over multiple rounds, executed code, processed files, and inspected figures.

## 2 Purposes and stages of use

A-01 Problem interpretation and modeling discussion. AI helped organize the relationships among the four tasks, inputs and outputs, information availability, costs, and storage constraints. It also supported discussion of model formulation and implementation boundaries. This work corresponds to the problem analysis, data interpretation, common model, and Q1-Q4 model sections.

A-02 Data processing and code implementation. AI helped interpret source fields and time keys, generated or modified model, optimization, execution, ledger, and validation code, diagnosed errors, and ran programs. The outputs include processing scripts, Q1-Q4 code, execution ledgers, and validation records.

A-03 Experiments and result analysis. AI participated in implementing, executing, and organizing annual policy comparisons, correction methods, historical sensitivity checks, and block-based interval analysis. It also helped analyze costs, emergency purchases, storage states, and negative results. Earlier sensitivity experiments concern their stated historical workflows; they do not establish sensitivity of the current reserve controller.

A-04 Figure production. AI selected figure templates, wrote and executed plotting code, and produced architecture diagrams, comparison charts, and composite scientific figures. It checked time keys, units, font sizes, and consistency between figures and text. The outputs include figures, plotting code, data mappings, and quality records.

A-05 Manuscript writing and reference checking. AI contributed substantive drafts and revisions of the abstract, main text, equations and algorithm descriptions, result interpretation, and limitations. It also helped polish English and check reference sources. These contributions extend across the manuscript and reference list.

A-06 Layout and supporting materials. AI assembled the manuscript, checked figure and table numbering and sources, inspected PDF pages, organized links to result workbooks, and prepared this disclosure. The outputs include build scripts, page-review reports, supporting-material indexes, and AI-use documentation.

## 3 Principal prompts and use process

This section summarizes the principal requests and iterative work in Codex; it is not a complete verbatim transcript.

### A-01 Problem interpretation and models

Inputs included the competition problem, attachments, existing plans, earlier drafts, and subsequent corrections. The principal request was to organize the requirements and constraints, discuss and implement the existing approach, and explain key interpretations and available information. AI produced task relationships, candidate formulations, equations, and algorithm explanations. Our team selected the initial models manually. AI participated in later formulation and implementation discussions, and our team decided the final approach.

### A-02 Data and code

The principal request was to complete and run model code, preserve original time keys, diagnose errors, and cross-check energy, costs, result workbooks, and figures. AI generated or modified data-reading, solver, and policy-execution code and wrote separate read-back and consistency-check scripts. The process involved execution, output inspection, correction, and rerunning. Outputs include model programs, interval ledgers, tests, and read-back records. The final code and version records identify the adopted files.

### A-03 Experiments and analysis

The principal request was to investigate storage-control improvements, annual paired comparisons, and correction methods while retaining negative months and intervals crossing zero. A reduction in emergency purchases was not assumed in advance. Recorded work includes analysis after 22 annual trajectories had completed and comparison figures generated from those results. AI contributed interpretations and suggestions for selecting approaches. Later figure and manuscript revisions mainly read the existing results.

### A-04 Figures

The principal request was to create informative composite scientific figures from real inputs, use English labels, retain the original observations, and avoid smoothing or shifting dispatch time keys. AI generated PNG and SVG files and inspected the rendered figures. Outputs include monthly ridgelines of annual daily summaries, a Q1 dispatch clock, and composite figures in later sections. The ridgelines aggregate all 144 intervals in each of 365 complete days before showing monthly distributions of three daily quantities. Their density curves are descriptive.

### A-05 Writing and references

The principal request was to revise the manuscript using saved results and review comments, explain equations, algorithms, results, and limitations, check citation sources, and make the language and structure consistent. AI produced section drafts, the abstract, result analyses, and revisions. It also checked reference metadata and the intended use of citations. Our team decided which references to adopt.

### A-06 Layout and disclosure

The principal request was to integrate figures, inspect every rendered page, fix isolated headings or paragraphs interrupted by floating figures, retain source mappings and file hashes, and disclose substantive AI participation accurately. AI produced build files, PDFs, page-review reports, and this document. AI inspected rendered pages and recorded its observations.

## 4 Adoption and human modification and verification

Our team reviewed the work throughout the process. We selected the initial models manually, reviewed the first mixed-integer linear programming (MILP) experiment after completion, and reviewed the subsequent work for each task. When we found the AI-implemented Q2 policy unsatisfactory and too conservative, we made manual adjustments. Relevant programs were run for validation. This description of manual involvement follows the team member's account reproduced in E-01.

For A-01 to A-03, the reported human actions were initial model selection, review of the first MILP experiment and later tasks, and adjustments to the Q2 implementation after inspecting its conservative behavior. The retained program outputs provide computational evidence; they do not by themselves establish who manually checked every output.

For A-04, the team requested more informative figures and agreed to the proposed front-section visualizations. AI produced the plots from recorded inputs and performed data and visual checks. Figure revisions addressed observed font size, density-tail and layout problems. These recorded AI checks are separate from human adoption decisions.

For A-05 to A-06, the team requested substantive manuscript revisions and specified the intended disclosures and language. AI drafted and revised the text, checked source relationships, and inspected rendered pages. The team member reported review throughout the work; this record does not reinterpret automated comparisons or AI page inspections as manual review.

Program-based checks provide supporting evidence. The front-figure data report compared three actual-data series from Attachments 2 and 4, each containing 52,560 values and their time keys. It also checked the Q1 source sequences, energy recurrence, costs, and figure mappings. The annual ridgeline data retain 365 days and 1,095 original points across three panels. Manuscript build and page-coverage reports record file consistency and rendering checks. These automated checks and AI visual inspections support human review and are recorded separately from our team's judgment and review.

## 5 Representative interactions

E-01 relates to A-01 to A-03. Translated excerpt from a team member's account of human involvement: "First, I selected the initial models myself. I also reviewed the first MILP experiment after it was completed, and I reviewed every subsequent task. In particular, when I found that the AI-implemented policy for Question 2 was not satisfactory and was too conservative, I made many manual adjustments." This account describes manual model selection, review of the first MILP experiment and each subsequent task, and adjustment of the Q2 policy.

E-02 relates to A-04. Translated excerpt from an actual team request: "These figures are all quite far back. Could we also add some more advanced figures near the beginning of the paper?" AI then proposed monthly ridgelines of annual daily distributions and a Q1 dispatch clock, adapted the real data, executed plotting code, and inspected the figures. Our team agreed to include both figures in the front part of the paper. They were incorporated as Figures 3 and 4 in the subsequent manuscript. The figures and separate data-check reports retain sources, original observations, and verification records.

## 6 Review before submission

Before submission, the team must review the final manuscript, programs, figures, workbooks and this disclosure, confirm actual adoption and human verification of AI outputs, and check the applicable submission requirements. This final review is a team responsibility; automated consistency reports cannot certify that it has occurred. The detailed supporting document is this PDF.

