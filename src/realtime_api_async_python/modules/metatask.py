from typing import TypeVar, Generic
from pydantic import BaseModel, Field

# Define a generic TypeVar for agents
A = TypeVar("A", bound=BaseModel)

# Base task type
class TaskBase(Generic[A], BaseModel):
    agent_type: A = Field(..., description="Type of agent required to execute the task.")
    details: str = Field(..., description="Detailed information about the task.")
    
    # XML Prompt template as a class attribute
    prompt_template: str = """
    <task>
        <type>BaseTask</type>
        <instructions>
            <instruction>Define the task-specific behavior.</instruction>
        </instructions>
    </task>
    """

    class Config:
        arbitrary_types_allowed = True

# Specific task types with embedded XML prompts

class ProblemAnalysisTask(TaskBase[A]):
    description: str = Field(..., description="Description of the problem to analyze.")

    prompt_template: str = """
    <task>
        <type>ProblemAnalysis</type>
        <instructions>
            <instruction>Restate the user's request in precise terms to verify understanding.</instruction>
            <instruction>Identify implicit constraints or ambiguities in the request.</instruction>
            <instruction>Break down abstract requirements into concrete specifications.</instruction>
        </instructions>
        <exemplar>
            <user-request>
                "Create a bash script that extracts even and odd numbers from a string."
            </user-request>
            <response>
                <restatement>The task requires separating odd and even numbers from an input string format.</restatement>
                <constraints>Ensure no spaces in input, handle malformed strings gracefully, and output arrays of numbers.</constraints>
                <concrete-specification>Input: string with numbers separated by commas. Output: Two arrays [odd_numbers], [even_numbers].</concrete-specification>
            </response>
        </exemplar>
    </task>
    """

class TaskDecompositionTask(TaskBase[A]):
    subtasks: list[str] = Field(..., description="List of subtasks derived from the problem.")

    prompt_template: str = """
    <task>
        <type>TaskDecomposition</type>
        <instructions>
            <instruction>Decompose the problem into manageable subtasks.</instruction>
            <instruction>Order the subtasks logically, ensuring dependencies are clear.</instruction>
            <instruction>Allow for context-aware adjustments in subtask granularity based on complexity.</instruction>
        </instructions>
        <exemplar>
            <problem>
                Extract even and odd numbers from an input string.
            </problem>
            <decomposition>
                <subtask>Capture input string as an argument.</subtask>
                <subtask>Remove spaces from the input.</subtask>
                <subtask>Parse numbers and separate odd from even values.</subtask>
                <subtask>Output two arrays: [odd_numbers] and [even_numbers].</subtask>
            </decomposition>
        </exemplar>
    </task>
    """

class TaskCompletionTask(TaskBase[A]):
    success: bool = Field(..., description="Indicates if the task was completed successfully.")
    result: dict = Field(..., description="The result of the task.")

    prompt_template: str = """
    <task>
        <type>TaskCompletion</type>
        <instructions>
            <instruction>Execute the decomposed subtasks in order.</instruction>
            <instruction>Use step-by-step reasoning to generate results.</instruction>
            <instruction>Return the outputs alongside a success flag.</instruction>
        </instructions>
        <exemplar>
            <problem>
                Extract even and odd numbers from an input string.
            </problem>
            <execution>
                <step>Input string captured: "1,2,3,4,5,6".</step>
                <step>Spaces removed (if any): "1,2,3,4,5,6".</step>
                <step>Parsed numbers: [1, 2, 3, 4, 5, 6].</step>
                <step>Separated odd and even: [1, 3, 5], [2, 4, 6].</step>
            </execution>
            <output>
                <success>true</success>
                <results>
                    <odd>[1,3,5]</odd>
                    <even>[2,4,6]</even>
                </results>
            </output>
        </exemplar>
    </task>
    """

class AlternativeProposalTask(TaskBase[A]):
    alternatives: list[str] = Field(..., description="Alternative approaches to the task.")

    prompt_template: str = """
    <task>
        <type>AlternativeProposal</type>
        <instructions>
            <instruction>Generate diverse alternatives for solving the problem.</instruction>
            <instruction>Explain the reasoning for each alternative approach.</instruction>
        </instructions>
        <exemplar>
            <problem>
                Extract even and odd numbers from an input string.
            </problem>
            <alternatives>
                <option>
                    <method>Use Python regex to extract numbers and filter odd/even using modulus.</method>
                    <reason>Regex simplifies parsing strings with unexpected formats.</reason>
                </option>
                <option>
                    <method>Use a bash script with `awk` to filter numbers.</method>
                    <reason>Suitable for environments without Python installed.</reason>
                </option>
            </alternatives>
        </exemplar>
    </task>
    """

class SelfEvaluationTask(TaskBase[A]):
    evaluation: str = Field(..., description="Self-assessment of task performance.")

    prompt_template: str = """
    <task>
        <type>SelfEvaluation</type>
        <instructions>
            <instruction>Evaluate the correctness of the solution.</instruction>
            <instruction>Provide explicit feedback on potential improvements.</instruction>
        </instructions>
        <exemplar>
            <problem>
                Extract even and odd numbers from an input string.
            </problem>
            <evaluation>
                <validation>Input "1,2,3,4,5,6" produced expected output [1,3,5], [2,4,6].</validation>
                <feedback>No issues detected, but input edge cases should be tested.</feedback>
            </evaluation>
        </exemplar>
    </task>
    """

class SelfCorrectionTask(TaskBase[A]):
    corrections: str = Field(..., description="Proposed corrections for future improvement.")

    prompt_template: str = """
    <task>
        <type>SelfCorrection</type>
        <instructions>
            <instruction>Identify and correct errors in previous outputs.</instruction>
            <instruction>Iterate until a satisfactory solution is produced.</instruction>
        </instructions>
        <exemplar>
            <problem>
                Extract even and odd numbers from an input string.
            </problem>
            <initial-output>
                <odd>[1,3]</odd>
                <even>[2,4,5,6]</even>
            </initial-output>
            <correction>
                <issue>Odd numbers list incomplete; 5 was misclassified as even.</issue>
                <fix>Adjust modulus operation to correctly classify numbers.</fix>
            </correction>
            <corrected-output>
                <odd>[1,3,5]</odd>
                <even>[2,4,6]</even>
            </corrected-output>
        </exemplar>
    </task>
    """
 