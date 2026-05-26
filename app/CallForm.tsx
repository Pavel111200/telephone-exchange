'use client';

import { useState } from "react";
import { CiSquarePlus } from "react-icons/ci";
import { JSX } from "react/jsx-runtime";

const CallForm = ({
  sendInformation,
}: {
  sendInformation: (formData: FormData) => void;
}) => {
  const [numberOfQuestions, setNumberOfQuestions] = useState(2);

  function createQuestionInputs(count: number) : JSX.Element[] {
    const elements = [];

    for (let index = 0; index < count; index++) {
      const element = <textarea
            id={`question-${index + 1}`}
            name={`question${index + 1}`}
            rows={2}
            key={index + 1}
            className="bg-white text-black rounded-xs"
          ></textarea>

      elements.push(element);
    }

    return elements;
  }

  return (
    <form
      action={sendInformation}
      className="flex flex-col bg-black p-4 gap-4 rounded-md w-4/5"
    >
      <div className="flex flex-col">
        <label htmlFor="phone-number" className="text-white">
          Phone number
        </label>

        <input
          type="text"
          id="phone-number"
          name="phoneNumber"
          required
          className="bg-white text-black rounded-xs h-7"
        />
      </div>

      <div className="flex flex-col">
        <label htmlFor="link" className="text-white">
          Link to job posting
        </label>

        <input
          type="text"
          id="link"
          name="link"
          required
          className="bg-white text-black rounded-xs h-7"
        />
      </div>

      <div className="flex flex-col">
        <label className="text-white">Questions</label>

        <div className="flex flex-col gap-3">
          {createQuestionInputs(numberOfQuestions)}
          <CiSquarePlus size={36} onClick={() => setNumberOfQuestions(count => count + 1)} className="cursor-pointer"/>
        </div>
      </div>

      <button
        type="submit"
        className="w-fit self-end px-5 py-2 bg-white text-black rounded-sm"
      >
        Submit
      </button>
    </form>
  );
};

export default CallForm;
