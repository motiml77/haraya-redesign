export interface Book {
  id: string;
  title: string;
  description: string;
  orderIndex: number;
  createdAt: string;
  updatedAt: string;
}

export interface Section {
  id: string;
  bookId: string;
  parentId: string | null;
  title: string;
  orderIndex: number;
  depth: number;

  // Content fields (optional)
  contentBlocks?: ContentBlock[];
  originalText?: string;       // Legacy - use contentBlocks instead
  commentary?: Commentary[];   // Legacy - use contentBlocks instead
  comments?: Comment[];
  questionsForRabbi?: QuestionForRabbi[];
  isEdited?: boolean;
  tags?: string[];

  // Denormalized
  bookTitle?: string;

  createdAt: string;
  updatedAt: string;
}

export interface ContentBlock {
  id: string;
  sourceText: string;
  commentaryText: string;
}

export interface Commentary {
  id: number | string;
  text: string;
  sources?: { id: string; text: string; link: string }[];
}

export interface Comment {
  id: number | string;
  author: string;
  date: string;
  text: string;
  replies: Reply[];
  resolved?: boolean;
  resolvedBy?: string;
  resolvedDate?: string;
}

export interface ReplyAttachment {
  url: string;
  name: string;
  type: 'pdf' | 'docx' | 'image';
  size: number;
}

export interface Reply {
  id: number | string;
  author: string;
  date: string;
  text: string;
  audioUrl?: string;
  attachments?: ReplyAttachment[];
}

export interface QuestionForRabbi {
  id: number | string;
  author: string;
  date: string;
  text: string;
  paragraphTitle: string;
  selectedText?: string;
  replies?: Reply[];
  resolved?: boolean;
  resolvedBy?: string;
  resolvedDate?: string;
}

export interface ContactMessage {
  id: string;
  name: string;
  email?: string;
  subject: string;
  message: string;
  date: string;
  createdAt: string;
  replies: Reply[];
  resolved?: boolean;
  resolvedBy?: string;
  resolvedDate?: string;
}

export interface Announcement {
  id: string;
  title: string;
  content: string;
  type: 'editors' | 'all';
  createdBy: string;
  createdByUid: string;
  createdAt: string;
  readBy: string[];
}
