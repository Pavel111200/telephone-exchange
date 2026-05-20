type OutputProps = {
  answer: string
}

export default function Output({ answer }: OutputProps) {
  return (
    <div className="w-4/5 mt-6 bg-white border border-zinc-300 rounded-md p-4 shadow-sm">
      <h2 className="text-xl font-bold mb-3 text-black">
        AI Answer  
      </h2>

      <p className="text-black whitespace-pre-wrap">
        {answer}
      </p>
    </div>
  )
}