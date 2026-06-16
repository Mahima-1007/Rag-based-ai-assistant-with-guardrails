import { useState, useEffect, useCallback } from 'react';
import { fetchDocuments, deleteDocument } from '../documents/documentService';
import toast from 'react-hot-toast';

export default function useDocuments() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadDocs = useCallback(async () => {
    try {
      setLoading(true);
      const docs = await fetchDocuments();
      setDocuments(docs);
    } catch (err) {
      toast.error('Failed to load documents');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocs();
  }, [loadDocs]);

  const removeDoc = async (id) => {
    try {
      await deleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
      toast.success('Document deleted successfully');
    } catch (err) {
      toast.error('Failed to delete document');
    }
  };

  return { documents, loading, loadDocs, removeDoc };
}
