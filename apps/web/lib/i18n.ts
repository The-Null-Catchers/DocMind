export type Locale = "en" | "ar";
export const messages = {
  en: {
    home: "Home", documents: "Documents", ai: "AI", study: "Study", notes: "Notes", flashcards: "Flashcards", quizzes: "Quizzes",
    search: "Search documents, chats, notes…", upload: "Upload", recent: "Recent documents", continue: "Continue reading",
    ask: "Ask DocMind", citation: "Sources", processing: "Processing", ready: "Ready", command: "Command palette"
  },
  ar: {
    home: "الرئيسية", documents: "المستندات", ai: "الذكاء", study: "الدراسة", notes: "الملاحظات", flashcards: "البطاقات", quizzes: "الاختبارات",
    search: "ابحث في المستندات والمحادثات والملاحظات…", upload: "رفع ملف", recent: "المستندات الأخيرة", continue: "متابعة القراءة",
    ask: "اسأل DocMind", citation: "المصادر", processing: "قيد المعالجة", ready: "جاهز", command: "لوحة الأوامر"
  }
} as const;
