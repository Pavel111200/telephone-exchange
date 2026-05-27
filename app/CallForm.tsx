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
            name='questions'
            rows={2}
            key={index + 1}
            className="bg-gray-200/75 text-black rounded-sm p-1"
          ></textarea>

      elements.push(element);
    }

    return elements;
  }

  return (
    <form
      action={sendInformation}
      className="flex flex-col bg-white shadow-xl/30 p-4 gap-4 rounded-md w-1/2"
    >
      <div className="flex flex-col">
        <label htmlFor="phone-number" className="text-black">
          Phone number:
        </label>

        <input
          type="text"
          id="phone-number"
          name="phoneNumber"
          required
          className="bg-gray-200/75 text-black rounded-sm h-7 p-1"
        />
      </div>

      <div className="flex flex-col">
        <label htmlFor="link" className="text-black">
          Link to job posting:
        </label>

        <input
          type="text"
          id="link"
          name="link"
          required
          className="bg-gray-200/75 text-black rounded-sm h-7 p-1"
        />
      </div>

      <div className="flex flex-col">
        <label className="text-black">Questions:</label>

        <div className="flex flex-col gap-3">
          {createQuestionInputs(numberOfQuestions)}
          <CiSquarePlus size={36} onClick={() => setNumberOfQuestions(count => count + 1)} className="cursor-pointer text-purple"/>
        </div>
      </div>

      <button
        type="submit"
        className="px-5 py-2 bg-purple text-white rounded-sm"
      >
        Submit
      </button>
    </form>
  );
};

export default CallForm;
