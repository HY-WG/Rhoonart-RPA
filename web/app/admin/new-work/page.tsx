export default function NewWorkPage() {
  return (
    <div className="p-8">
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-8 py-6 border-b border-gray-100">
          <h1 className="text-2xl font-bold text-gray-900">신규작품 등록</h1>
        </div>

        <form className="px-8 py-6 space-y-5">
          {/* 작품명 */}
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">작품명</label>
            <input
              type="text"
              placeholder="작품명을 입력하세요"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-400 focus:border-transparent"
            />
          </div>

          {/* 아티스트 */}
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">아티스트</label>
            <input
              type="text"
              placeholder="아티스트명을 입력하세요"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-400 focus:border-transparent"
            />
          </div>

          {/* 썸네일 이미지 */}
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">썸네일 이미지</label>
            <div className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-500 bg-white">
              <input type="file" accept="image/*" className="text-sm text-gray-500" />
            </div>
          </div>

          {/* 설명 */}
          <div>
            <label className="block text-sm text-gray-700 mb-1.5">설명</label>
            <textarea
              rows={5}
              placeholder="작품 설명을 입력하세요"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-teal-400 focus:border-transparent resize-none"
            />
          </div>

          {/* 버튼 */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              className="px-6 py-2.5 border border-gray-300 text-sm text-gray-600 rounded-lg hover:bg-gray-50 transition-colors"
            >
              취소
            </button>
            <button
              type="submit"
              className="px-6 py-2.5 bg-teal-500 text-white text-sm font-medium rounded-lg hover:bg-teal-600 transition-colors"
            >
              등록
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
