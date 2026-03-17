import { BookLoader } from '@/components/BookLoader';

export default function Loading() {
  return (
    <div className="min-h-screen bg-[#FAF8F5] flex items-center justify-center">
      <BookLoader />
    </div>
  );
}
