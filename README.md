# Receipt OCR Processing API

A FastAPI-based API that processes receipt images and extracts relevant transaction data automatically using OCR and LLM-powered parsing.

## Overview

This project was built to automate the reading of payment receipts and convert unstructured image data into structured information that can be used inside operational workflows.

The API receives a receipt image, transcribes the visible content, cleans OCR noise, and extracts key fields such as:

- Transaction ID
- Date and time
- Branch / location
- Amount

## Why I Built This

In many business workflows, receipts are still reviewed manually. This creates delays, repetitive work, and a higher chance of human error.

This API was created to reduce manual effort and make receipt processing faster, more consistent, and easier to integrate into internal systems.

## Tech Stack

- Python
- FastAPI
- OpenAI API
- Pydantic
- HTTPX

## Main Features

- Upload and process receipt images
- OCR-based text transcription from receipt images
- Text cleanup for noisy OCR output
- Structured extraction of relevant transaction fields
- API-ready workflow for integration into larger systems

## Project Structure

```text
.
├── main.py
├── requirements.txt
├── README.md
└── .gitignore

