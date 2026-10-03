import pandas as pd
import os
import json
import streamlit as st
from pypdf import PdfReader
from dotenv import load_dotenv
from openai import OpenAI

# -------------------------
# SETUP
# -------------------------

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(
    page_title="Document Extractor",
    page_icon="📄",
    layout="centered"
)

# -------------------------
# TEMPLATES
# -------------------------

templates = {
    "Custom": [
        "",
        "",
        ""
    ],

    "Contract Review": [
        "Company / parties",
        "Contract value",
        "Start date",
        "Expiry date",
        "Payment terms",
        "Termination terms",
        "Renewal terms",
        "Key obligations"
    ],

    "Lecture / Study Notes": [
        "Main topics",
        "Key concepts",
        "Important definitions",
        "Important people or theories",
        "Important dates",
        "Key facts",
        "Potential revision topics"
    ],

    "Tender Analysis": [
        "Project name",
        "Location",
        "Contract value",
        "Submission deadline",
        "Scope of work",
        "Required qualifications",
        "Insurance requirements",
        "Key requirements"
    ],

    "Invoice": [
        "Supplier name",
        "Invoice number",
        "Invoice date",
        "Due date",
        "Subtotal",
        "Tax",
        "Total amount",
        "Payment details"
    ]
}
# -------------------------
# CUSTOM TEMPLATE STORAGE
# -------------------------

CUSTOM_TEMPLATE_FILE = "custom_templates.json"


def load_custom_templates():

    if os.path.exists(CUSTOM_TEMPLATE_FILE):

        try:
            with open(
                CUSTOM_TEMPLATE_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                return json.load(file)

        except:
            return {}

    return {}


def save_custom_templates(custom_templates):

    with open(
        CUSTOM_TEMPLATE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            custom_templates,
            file,
            indent=4
        )


custom_templates = load_custom_templates()

templates.update(custom_templates)
# -------------------------
# SESSION STATE
# -------------------------

if "fields" not in st.session_state:
    st.session_state.fields = ["", "", ""]

if "current_template" not in st.session_state:
    st.session_state.current_template = "Custom"

# -------------------------
# HEADER
# -------------------------

st.title("Document Extractor")

st.write(
    "Upload a document and choose exactly what information you want to extract."
)
# -------------------------
# CREATE CUSTOM TEMPLATE
# -------------------------

with st.expander("Create Custom Template"):

    template_name = st.text_input(
        "Template name",
        placeholder="e.g. Supplier Contract Review"
    )

    template_fields_text = st.text_area(
        "Fields to extract",
        placeholder="""Supplier name
Contract value
Start date
Expiry date
Payment terms
Termination notice"""
    )

    if st.button("Save Template"):

        new_fields = [
            field.strip()
            for field in template_fields_text.splitlines()
            if field.strip()
        ]

        if not template_name.strip():

            st.error("Please enter a template name.")

        elif len(new_fields) == 0:

            st.error("Please add at least one field.")

        else:

            custom_templates[template_name.strip()] = new_fields

            save_custom_templates(custom_templates)

            st.success(
                f"Template '{template_name}' saved."
            )

            st.rerun()
# -------------------------
# FILE UPLOAD
# -------------------------

uploaded_file = st.file_uploader(
    "Upload PDF",
    type=["pdf"]
)

# -------------------------
# TEMPLATE SELECTOR
# -------------------------

st.subheader("Extraction Template")

selected_template = st.selectbox(
    "Choose a template",
    list(templates.keys())
)

# Load template only when selection changes
if selected_template != st.session_state.current_template:

    st.session_state.fields = templates[selected_template].copy()
    st.session_state.current_template = selected_template

    # Clear old text input state
    keys_to_remove = [
        key for key in st.session_state
        if key.startswith("field_input_")
    ]

    for key in keys_to_remove:
        del st.session_state[key]

    st.rerun()

# -------------------------
# EXTRACTION FIELDS
# -------------------------

st.subheader("What do you want to extract?")

updated_fields = []

for i, field_value in enumerate(st.session_state.fields):

    field = st.text_input(
        f"Field {i + 1}",
        value=field_value,
        placeholder="e.g. Contract value",
        key=f"field_input_{i}"
    )

    updated_fields.append(field)

st.session_state.fields = updated_fields

# -------------------------
# ADD / REMOVE FIELD
# -------------------------

col1, col2 = st.columns(2)

with col1:

    if st.button("+ Add Field"):

        st.session_state.fields.append("")
        st.rerun()

with col2:

    if st.button("− Remove Field"):

        if len(st.session_state.fields) > 1:

            st.session_state.fields.pop()

            last_key = (
                f"field_input_{len(st.session_state.fields)}"
            )

            if last_key in st.session_state:
                del st.session_state[last_key]

            st.rerun()

# Remove blank fields before extraction
fields = [
    field.strip()
    for field in st.session_state.fields
    if field.strip()
]

# -------------------------
# EXTRACTION
# -------------------------

if st.button(
    "Extract Information",
    type="primary"
):

    if uploaded_file is None:

        st.error(
            "Please upload a PDF."
        )

    elif len(fields) == 0:

        st.error(
            "Please enter at least one field."
        )

    else:

        # -------------------------
        # READ PDF
        # -------------------------

        with st.spinner(
            "Reading document..."
        ):

            reader = PdfReader(
                uploaded_file
            )

            document_text = ""

            for page_number, page in enumerate(
                reader.pages,
                start=1
            ):

                text = (
                    page.extract_text()
                    or ""
                )

                document_text += (
                    f"\n--- PAGE {page_number} ---\n{text}"
                )

        field_list = "\n".join(
            f"- {field}"
            for field in fields
        )

        # -------------------------
        # SEND TO AI
        # -------------------------

        with st.spinner(
            "Extracting information..."
        ):

            response = client.responses.create(

                model="gpt-5-mini",

                input=f"""
You are a document extraction system.

Extract these fields:

{field_list}

Return ONLY valid JSON.

Use this exact structure:

{{
    "results": [
        {{
            "field": "Company name",
            "value": "Example Ltd",
            "page": 1
        }}
    ]
}}

RULES:

- Return one result for every requested field.
- Only use information from the document.
- Never guess.
- If information cannot be found, use "Not found".
- If not found, set page to null.
- Page must be a number, not text.
- Do not include markdown.
- Do not include explanations outside the JSON.

DOCUMENT:

{document_text}
"""
            )

        # -------------------------
        # PARSE RESPONSE
        # -------------------------

        try:

            data = json.loads(
                response.output_text
            )

            st.success(
                "Extraction complete"
            )

            st.subheader("Results")

            # -------------------------
            # RESULT CARDS
            # -------------------------

            for result in data["results"]:

                field = result.get(
                    "field",
                    ""
                )

                value = result.get(
                    "value",
                    "Not found"
                )

                page = result.get(
                    "page"
                )

                with st.container(
                    border=True
                ):

                    st.markdown(
                        f"**{field}**"
                    )

                    st.write(value)

                    if page is not None:

                        st.caption(
                            f"Source: Page {page}"
                        )

                    else:

                        st.caption(
                            "Source: Not found"
                        )

            # -------------------------
            # CSV EXPORT
            # -------------------------

            df = pd.DataFrame(
                data["results"]
            )

            csv = df.to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(
                label="Download Results as CSV",
                data=csv,
                file_name="extracted_results.csv",
                mime="text/csv"
            )

        except json.JSONDecodeError:

            st.error(
                "The AI returned an invalid response. Please try again."
            )

            with st.expander(
                "Technical details"
            ):

                st.text(
                    response.output_text
                )