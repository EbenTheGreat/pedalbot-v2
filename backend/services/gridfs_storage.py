"""
GridFS storage for PDF files.

Enables sharing PDFs between Railway services (API + Celery worker)
without needing a shared filesystem volume.

Usage:
    from backend.services.gridfs_storage import GridFSStorage

    # Upload
    gridfs_id = await GridFSStorage.upload_pdf(db, "manual.pdf", content, "manual_123")

    # Download
    filename, data = await GridFSStorage.download_pdf(db, "manual_123")

    # Delete
    await GridFSStorage.delete_pdf(db, "manual_123")
"""

import logging
from typing import Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket

logger = logging.getLogger(__name__)

BUCKET_NAME = "pdfs"


class GridFSStorage:
    """Async GridFS helper for PDF storage in MongoDB."""

    @staticmethod
    async def upload_pdf(
        db: AsyncIOMotorDatabase,
        filename: str,
        content: bytes,
        manual_id: str,
    ) -> str:
        """
        Upload a PDF to GridFS.

        Args:
            db: Motor database instance
            filename: Original PDF filename
            content: Raw PDF bytes
            manual_id: Manual ID for lookup

        Returns:
            GridFS file ID as string
        """
        bucket = AsyncIOMotorGridFSBucket(db, bucket_name=BUCKET_NAME)

        gridfs_id = await bucket.upload_from_stream(
            filename,
            content,
            metadata={
                "manual_id": manual_id,
                "content_type": "application/pdf",
                "size_bytes": len(content),
            },
        )

        logger.info(
            f"Uploaded PDF to GridFS: {filename} ({len(content)} bytes) "
            f"manual_id={manual_id}, gridfs_id={gridfs_id}"
        )
        return str(gridfs_id)

    @staticmethod
    async def download_pdf(
        db: AsyncIOMotorDatabase,
        manual_id: str,
    ) -> Optional[Tuple[str, bytes]]:
        """
        Download a PDF from GridFS by manual_id.

        Args:
            db: Motor database instance
            manual_id: Manual ID to look up

        Returns:
            Tuple of (filename, bytes) or None if not found
        """
        # Look up the GridFS file by manual_id metadata
        files_collection = db[f"{BUCKET_NAME}.files"]
        file_doc = await files_collection.find_one(
            {"metadata.manual_id": manual_id}
        )

        if not file_doc:
            logger.warning(f"No GridFS file found for manual_id={manual_id}")
            return None

        bucket = AsyncIOMotorGridFSBucket(db, bucket_name=BUCKET_NAME)

        # Download the file content
        from io import BytesIO

        stream = BytesIO()
        await bucket.download_to_stream(file_doc["_id"], stream)
        stream.seek(0)

        filename = file_doc.get("filename", f"{manual_id}.pdf")
        data = stream.read()

        logger.info(
            f"Downloaded PDF from GridFS: {filename} ({len(data)} bytes) "
            f"manual_id={manual_id}"
        )
        return filename, data

    @staticmethod
    async def delete_pdf(
        db: AsyncIOMotorDatabase,
        manual_id: str,
    ) -> bool:
        """
        Delete a PDF from GridFS by manual_id.

        Args:
            db: Motor database instance
            manual_id: Manual ID to look up

        Returns:
            True if deleted, False if not found
        """
        files_collection = db[f"{BUCKET_NAME}.files"]
        file_doc = await files_collection.find_one(
            {"metadata.manual_id": manual_id}
        )

        if not file_doc:
            logger.warning(f"No GridFS file to delete for manual_id={manual_id}")
            return False

        bucket = AsyncIOMotorGridFSBucket(db, bucket_name=BUCKET_NAME)
        await bucket.delete(file_doc["_id"])

        logger.info(f"Deleted PDF from GridFS: manual_id={manual_id}")
        return True
