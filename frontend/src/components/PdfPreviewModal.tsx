import { useEffect } from "react";
import { Modal } from "antd";

type PdfPreviewModalProps = {
  title: string;
  url: string;
  open: boolean;
  onClose: () => void;
};

export const PdfPreviewModal = ({ title, url, open, onClose }: PdfPreviewModalProps) => {
  useEffect(() => {
    return () => {
      if (url) {
        URL.revokeObjectURL(url);
      }
    };
  }, [url]);

  return (
    <Modal title={title} open={open} onCancel={onClose} footer={null} width="86vw" destroyOnClose>
      {url ? <iframe className="pdf-preview-frame" src={url} title={title} /> : null}
    </Modal>
  );
};
