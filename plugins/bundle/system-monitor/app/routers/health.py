# -*- coding: utf-8 -*-
"""Health check router."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
